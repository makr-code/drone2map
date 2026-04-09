"""Verarbeitungs-Pipeline mit Queue-basierter Event-Kommunikation."""
from __future__ import annotations
import logging
import os
import queue
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..core.exif_parser import ExifParser, ImageMetadata
from ..core.geo_utils import GeoUtils
from ..core.validators import ImageValidator
from ..core.project import Project
from .export import Exporter
from .odm_runner import OdmRunner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Typed pipeline events
# ---------------------------------------------------------------------------

@dataclass
class ProgressEvent:
    """Fortschritts-Update vom Hintergrund-Thread."""
    percent: float
    message: str


@dataclass
class MetadataEvent:
    """EXIF-Metadaten nach der Validierungsphase verfügbar."""
    metadata: list[ImageMetadata]


@dataclass
class DoneEvent:
    """Pipeline erfolgreich abgeschlossen."""
    result_paths: dict[str, str]


@dataclass
class ErrorEvent:
    """Nicht behandelbarer Fehler in der Pipeline."""
    message: str


# Union-Typ aller möglichen Events (nur zur Dokumentation, keine Laufzeit-Auswirkung)
PipelineEvent = ProgressEvent | MetadataEvent | DoneEvent | ErrorEvent


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Pipeline:
    """Koordiniert Validierung, EXIF-Extraktion und ODM-Verarbeitung.

    Alle Fortschritts- und Ergebnis-Meldungen werden über eine
    ``queue.Queue`` kommuniziert. Der GUI-Thread pollt diese Queue
    periodisch (z. B. via ``root.after``) und liest Events thread-sicher aus.
    """

    def __init__(self, project: Project):
        self.project = project
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._queue: queue.Queue[PipelineEvent] = queue.Queue()

    @property
    def event_queue(self) -> queue.Queue[PipelineEvent]:
        """Thread-sichere Queue für ``PipelineEvent``-Objekte."""
        return self._queue

    def run_async(self) -> None:
        """Startet die Pipeline im Hintergrund-Thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Fordert den Hintergrund-Thread auf, kooperativ zu stoppen."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Internas
    # ------------------------------------------------------------------

    def _put(self, event: PipelineEvent) -> None:
        self._queue.put(event)

    def _prog(self, pct: float, msg: str) -> None:
        self._put(ProgressEvent(pct, msg))

    def _run(self) -> None:
        try:
            self.project.status = "verarbeitung"
            self._prog(0.0, f"Validiere {len(self.project.image_paths)} Bilder...")

            s = self.project.settings
            results = ImageValidator(
                require_gps=True,
                max_size_mb=500,
            ).validate_batch(self.project.image_paths)
            valid_paths = [r.file_path for r in results if r.valid]
            if len(valid_paths) < 3:
                raise RuntimeError(f"Zu wenige valide Bilder: {len(valid_paths)}")

            if self._stop_event.is_set():
                return

            self._prog(5.0, "Lese EXIF-Metadaten...")
            parser = ExifParser()
            metadata = [parser.parse_file(p) for p in valid_paths]
            self._put(MetadataEvent(metadata))

            if self._stop_event.is_set():
                return

            self._prog(10.0, "Starte ODM-Verarbeitung...")
            runner = OdmRunner(host=s.node_host, port=s.node_port)
            opts = {
                "dsm": s.dsm,
                "dtm": s.dtm,
                "orthophoto-resolution": str(s.orthophoto_resolution),
                "feature-quality": s.feature_quality,
                "pc-quality": s.pc_quality,
                "mesh-octree-depth": str(s.mesh_octree_depth),
            }

            def odm_prog(pct: float, msg: str) -> None:
                self._prog(10.0 + pct * 0.85, msg)

            if runner.is_nodeodm_available():
                logger.info("Verbinde NodeODM auf %s:%s", s.node_host, s.node_port)
                result_paths = runner.run_via_nodeodm(
                    valid_paths,
                    self.project.output_dir,
                    options=opts,
                    progress_callback=odm_prog,
                    stop_event=self._stop_event,
                )
            else:
                logger.info("NodeODM nicht erreichbar – verwende ODM-CLI")
                self._prog(10.0, "NodeODM nicht verfügbar, verwende lokale ODM-CLI...")
                image_dir = self._stage_images(valid_paths, self.project.output_dir)
                result_paths = runner.run_via_cli(
                    image_dir,
                    self.project.output_dir,
                    options=opts,
                    progress_callback=odm_prog,
                    stop_event=self._stop_event,
                )

            if self._stop_event.is_set():
                return

            self._prog(95.0, "Exportiere und reprojiziere Ergebnisse...")
            lats = [m.latitude for m in metadata if m.latitude is not None]
            lons = [m.longitude for m in metadata if m.longitude is not None]
            target_epsg = GeoUtils.best_utm_epsg(lats, lons) if lats else None
            exporter = Exporter(self.project.output_dir)
            exported = exporter.export_all(result_paths, reproject_epsg=target_epsg)
            final_paths = exported if exported else result_paths
            exporter.create_export_report(final_paths, self.project.name)

            for k, v in final_paths.items():
                self.project.set_result(k, v)

            self.project.status = "fertig"
            self._prog(100.0, "Fertig!")
            self._put(DoneEvent(final_paths))

        except Exception as exc:
            logger.error("Pipeline-Fehler: %s", exc, exc_info=True)
            self.project.status = "fehler"
            self._put(ErrorEvent(str(exc)))

    @staticmethod
    def _stage_images(valid_paths: list[str], output_dir: str) -> str:
        """Gibt ein Verzeichnis zurück, in dem alle Bilder liegen.

        Wenn alle Bilder bereits in einem gemeinsamen Elternverzeichnis
        liegen, wird dieses zurückgegeben. Andernfalls werden die Bilder
        (via Symlink, Fallback auf Kopie) in ``{output_dir}/images/``
        zusammengeführt.
        """
        parents = {Path(p).parent for p in valid_paths}
        if len(parents) == 1:
            return str(next(iter(parents)))

        staging = Path(output_dir) / "images"
        staging.mkdir(parents=True, exist_ok=True)
        seen_names: dict[str, int] = {}
        for src in valid_paths:
            src_path = Path(src)
            stem, suffix = src_path.stem, src_path.suffix
            if stem in seen_names:
                seen_names[stem] += 1
                dest_name = f"{stem}_{seen_names[stem]}{suffix}"
            else:
                seen_names[stem] = 0
                dest_name = src_path.name
            dest = staging / dest_name
            if not dest.exists():
                try:
                    dest.symlink_to(src_path.resolve())
                except (OSError, NotImplementedError):
                    shutil.copy2(src, dest)
        logger.info("Bilder in Staging-Ordner zusammengeführt: %s", staging)
        return str(staging)
