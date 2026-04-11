"""ODM-Integration via pyodm (NodeODM) mit CLI-Fallback."""
from __future__ import annotations
import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class OdmRunner:
    def __init__(self, host: str = "localhost", port: int = 3000):
        self.host = host
        self.port = port

    def run_via_nodeodm(self, image_paths: list[str], output_dir: str,
                        options: Optional[dict] = None,
                        progress_callback: Optional[Callable[[float, str], None]] = None,
                        stop_event: Optional[threading.Event] = None,
                        max_retries: int = 3,
                        retry_delay: float = 5.0) -> dict[str, str]:
        try:
            from pyodm import Node
        except ImportError as exc:
            raise RuntimeError("pyodm nicht installiert: pip install pyodm") from exc
        opts = {"dsm": True, "dtm": True, "orthophoto-resolution": 5,
                "feature-quality": "high", "pc-quality": "high", "mesh-octree-depth": 12}
        if options:
            opts.update(options)
        node = Node(self.host, self.port)
        if progress_callback:
            progress_callback(0.0, "Verbinde NodeODM...")
        try:
            node.info()
        except Exception as exc:
            raise ConnectionError(f"NodeODM nicht erreichbar: {exc}") from exc
        if progress_callback:
            progress_callback(2.0, f"Lade {len(image_paths)} Bilder hoch...")
        task = node.create_task(image_paths, options=opts)
        consecutive_errors = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                task.cancel()
                return {}
            try:
                info = task.info()
                consecutive_errors = 0
            except Exception as exc:
                consecutive_errors += 1
                if consecutive_errors > max_retries:
                    raise RuntimeError(
                        f"NodeODM-Verbindung nach {max_retries} Versuchen verloren: {exc}"
                    ) from exc
                logger.warning(
                    "Abruf-Fehler (%d/%d): %s – warte %.0fs",
                    consecutive_errors, max_retries, exc, retry_delay,
                )
                if progress_callback:
                    progress_callback(-1.0, f"Verbindungsfehler – Wiederholungsversuch {consecutive_errors}/{max_retries}…")
                time.sleep(retry_delay)
                continue
            pct = info.progress or 0.0
            status = info.status.name if info.status else "UNBEKANNT"
            if progress_callback:
                progress_callback(pct, f"ODM: {status} ({pct:.1f}%)")
            if status == "COMPLETED":
                break
            if status in ("FAILED", "CANCELED"):
                raise RuntimeError(f"ODM fehlgeschlagen: {status}")
            time.sleep(3)
        if progress_callback:
            progress_callback(95.0, "Lade Ergebnisse...")
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        task.download_assets(str(out))
        results = self._collect_results(out)
        if progress_callback:
            progress_callback(100.0, "Fertig")
        return results

    def run_via_cli(self, image_dir: str, output_dir: str,
                    options: Optional[dict] = None,
                    progress_callback: Optional[Callable[[float, str], None]] = None,
                    stop_event: Optional[threading.Event] = None) -> dict[str, str]:
        opts: dict = {"dsm": True, "dtm": True, "orthophoto-resolution": "5",
                      "feature-quality": "high", "pc-quality": "high", "mesh-octree-depth": "12"}
        if options:
            opts.update(options)
        cmd = ["python", "-m", "odm"]
        for k, v in opts.items():
            if isinstance(v, bool):
                if v: cmd.append(f"--{k}")
            else:
                cmd.extend([f"--{k}", str(v)])
        cmd.extend(["--project-path", output_dir, image_dir])
        if progress_callback:
            progress_callback(0.0, "Starte ODM CLI...")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in proc.stdout or []:
            if stop_event is not None and stop_event.is_set():
                proc.terminate()
                return {}
            line = line.rstrip()
            logger.debug("ODM: %s", line)
            if progress_callback and line:
                progress_callback(-1.0, line)
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"ODM CLI exit {proc.returncode}")
        results = self._collect_results(Path(output_dir))
        if progress_callback:
            progress_callback(100.0, "Fertig")
        return results

    @staticmethod
    def _collect_results(out: Path) -> dict[str, str]:
        patterns = {
            "orthophoto": ["odm_orthophoto/odm_orthophoto.tif", "orthophoto.tif"],
            "dsm": ["odm_dem/dsm.tif", "dsm.tif"],
            "dtm": ["odm_dem/dtm.tif", "dtm.tif"],
            "pointcloud": ["odm_pointcloud/odm_georeferenced_model.laz", "pointcloud.laz"],
        }
        results: dict[str, str] = {}
        for key, cands in patterns.items():
            for c in cands:
                p = out / c
                if p.exists():
                    results[key] = str(p)
                    break
        return results

    def is_nodeodm_available(self) -> bool:
        try:
            from pyodm import Node
            Node(self.host, self.port).info()
            return True
        except Exception:
            return False
