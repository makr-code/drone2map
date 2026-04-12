"""Export-Funktionen: Ergebnisse kopieren, reprojizieren und in verschiedene Formate konvertieren."""
from __future__ import annotations
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class Exporter:
    """Exportiert ODM-Ergebnisse in verschiedene Formate und Zielverzeichnisse."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)

    def export_geotiff(self, src: str, dest_name: str, reproject_epsg: Optional[str] = None) -> str:
        """Kopiert/reprojiziert ein GeoTIFF in das Ausgabeverzeichnis."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        dest = self.output_dir / dest_name
        if reproject_epsg:
            try:
                import rasterio
                from rasterio.warp import calculate_default_transform, reproject, Resampling
                with rasterio.open(src) as src_ds:
                    transform, width, height = calculate_default_transform(
                        src_ds.crs, reproject_epsg, src_ds.width, src_ds.height, *src_ds.bounds)
                    meta = src_ds.meta.copy()
                    meta.update({"crs": reproject_epsg, "transform": transform,
                                 "width": width, "height": height})
                    with rasterio.open(dest, "w", **meta) as dst_ds:
                        for i in range(1, src_ds.count + 1):
                            reproject(source=rasterio.band(src_ds, i),
                                      destination=rasterio.band(dst_ds, i),
                                      src_transform=src_ds.transform, src_crs=src_ds.crs,
                                      dst_transform=transform, dst_crs=reproject_epsg,
                                      resampling=Resampling.nearest)
                logger.info("Reprojiziert: %s -> %s", src, dest)
            except ImportError:
                logger.warning("rasterio nicht verfügbar, einfache Kopie")
                shutil.copy2(src, dest)
        else:
            shutil.copy2(src, dest)
        return str(dest)

    def export_all(self, result_paths: dict[str, str], reproject_epsg: Optional[str] = None) -> dict[str, str]:
        """Exportiert alle Ergebnisdateien.

        GeoTIFF-Dateien werden kopiert/reprojiziert.  Andere Dateiformate
        (z. B. .laz Punktwolken) werden direkt in das Ausgabeverzeichnis kopiert.
        """
        _RASTER_EXTS = {".tif", ".tiff", ".geotiff"}
        exported: dict[str, str] = {}
        for key, src in result_paths.items():
            if not src or not Path(src).exists():
                continue
            suffix = Path(src).suffix
            dest_name = f"{key}{suffix}"
            try:
                if suffix.lower() in _RASTER_EXTS:
                    exported[key] = self.export_geotiff(src, dest_name, reproject_epsg)
                else:
                    self.output_dir.mkdir(parents=True, exist_ok=True)
                    dest = self.output_dir / dest_name
                    shutil.copy2(src, dest)
                    exported[key] = str(dest)
                    logger.info("Kopiert: %s -> %s", src, dest)
            except Exception as exc:
                logger.error("Export fehlgeschlagen %s: %s", key, exc)
        return exported

    def create_export_report(self, result_paths: dict[str, str], project_name: str) -> str:
        """Erstellt eine Textzusammenfassung und einen JSON-Bericht der Ergebnisse."""
        entries: dict[str, dict] = {}
        lines = [f"drone2map Exportbericht: {project_name}", "=" * 40]
        for key, path in result_paths.items():
            size_mb: Optional[float] = None
            p = Path(path)
            if p.exists():
                size_mb = p.stat().st_size / 1_048_576
                lines.append(f"  {key}: {path} ({size_mb:.1f} MB)")
            else:
                lines.append(f"  {key}: {path}")
            entries[key] = {"path": path, "size_mb": round(size_mb, 2) if size_mb is not None else None}

        self.output_dir.mkdir(parents=True, exist_ok=True)

        report = "\n".join(lines)
        report_path = self.output_dir / "export_report.txt"
        report_path.write_text(report, encoding="utf-8")

        json_report = {
            "project": project_name,
            "exported_at": datetime.now().isoformat(),
            "results": entries,
        }
        json_path = self.output_dir / "export_report.json"
        json_path.write_text(
            json.dumps(json_report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Exportbericht geschrieben: %s", report_path)
        return str(report_path)
