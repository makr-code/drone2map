"""Verarbeitungs-Pipeline."""
from __future__ import annotations
import logging, threading
from pathlib import Path
from typing import Callable, Optional
from ..core.exif_parser import ExifParser, ImageMetadata
from ..core.validators import ImageValidator
from ..core.project import Project
from .odm_runner import OdmRunner

logger = logging.getLogger(__name__)

class Pipeline:
    def __init__(self, project: Project):
        self.project = project
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def run_async(self,
                  on_progress: Optional[Callable[[float, str], None]] = None,
                  on_metadata: Optional[Callable[[list[ImageMetadata]], None]] = None,
                  on_finished: Optional[Callable[[dict[str, str]], None]] = None,
                  on_error: Optional[Callable[[str], None]] = None) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run,
            args=(on_progress, on_metadata, on_finished, on_error), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self, on_progress, on_metadata, on_finished, on_error) -> None:
        def prog(pct, msg):
            if on_progress: on_progress(pct, msg)
        try:
            prog(0.0, f"Validiere {len(self.project.image_paths)} Bilder...")
            results = ImageValidator().validate_batch(self.project.image_paths)
            valid_paths = [r.file_path for r in results if r.valid]
            if len(valid_paths) < 3:
                raise RuntimeError(f"Zu wenige valide Bilder: {len(valid_paths)}")
            if self._stop_event.is_set(): return
            prog(5.0, "Lese EXIF-Metadaten...")
            metadata = [ExifParser().parse_file(p) for p in valid_paths]
            if on_metadata: on_metadata(metadata)
            if self._stop_event.is_set(): return
            prog(10.0, "Starte ODM-Verarbeitung...")
            s = self.project.settings
            runner = OdmRunner(host=s.node_host, port=s.node_port)
            opts = {"dsm": s.dsm, "dtm": s.dtm,
                    "orthophoto-resolution": str(s.orthophoto_resolution),
                    "feature-quality": s.feature_quality,
                    "pc-quality": s.pc_quality,
                    "mesh-octree-depth": str(s.mesh_octree_depth)}
            def odm_prog(pct, msg): prog(10.0 + pct * 0.85, msg)
            result_paths = runner.run_via_nodeodm(valid_paths, self.project.output_dir,
                                                  options=opts, progress_callback=odm_prog)
            for k, v in result_paths.items():
                self.project.set_result(k, v)
            self.project.status = "fertig"
            prog(100.0, "Fertig!")
            if on_finished: on_finished(result_paths)
        except Exception as exc:
            logger.error("Pipeline-Fehler: %s", exc, exc_info=True)
            self.project.status = "fehler"
            if on_error: on_error(str(exc))
