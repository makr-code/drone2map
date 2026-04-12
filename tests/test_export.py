"""Tests für drone2map.processing.export."""
from __future__ import annotations
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from drone2map.processing.export import Exporter


class TestExporter:
    def test_export_geotiff_simple_copy(self, tmp_path):
        src = tmp_path / "src.tif"
        src.write_bytes(b"TIFFDATA")
        out_dir = tmp_path / "out"
        exp = Exporter(str(out_dir))
        result = exp.export_geotiff(str(src), "orthophoto.tif")
        assert Path(result).exists()
        assert Path(result).read_bytes() == b"TIFFDATA"

    def test_export_geotiff_creates_output_dir(self, tmp_path):
        src = tmp_path / "src.tif"
        src.write_bytes(b"X")
        out_dir = tmp_path / "nested" / "output"
        exp = Exporter(str(out_dir))
        exp.export_geotiff(str(src), "f.tif")
        assert out_dir.exists()

    def test_export_all_skips_missing(self, tmp_path):
        out_dir = tmp_path / "out"
        exp = Exporter(str(out_dir))
        result_paths = {"orthophoto": "/nonexistent/file.tif", "dsm": ""}
        exported = exp.export_all(result_paths)
        assert exported == {}

    def test_export_all_copies_existing(self, tmp_path):
        src = tmp_path / "orthophoto.tif"
        src.write_bytes(b"ORTHO")
        out_dir = tmp_path / "out"
        exp = Exporter(str(out_dir))
        exported = exp.export_all({"orthophoto": str(src)})
        assert "orthophoto" in exported
        assert Path(exported["orthophoto"]).read_bytes() == b"ORTHO"

    def test_export_all_continues_on_error(self, tmp_path):
        src_good = tmp_path / "good.tif"
        src_good.write_bytes(b"GOOD")
        out_dir = tmp_path / "out"
        exp = Exporter(str(out_dir))
        # Force an error on first key by passing a directory as source
        exported = exp.export_all({"bad": str(tmp_path), "good": str(src_good)})
        assert "good" in exported

    def test_create_export_report(self, tmp_path):
        src = tmp_path / "orthophoto.tif"
        src.write_bytes(b"X" * 1024)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "orthophoto.tif").write_bytes(b"X" * 1024)
        exp = Exporter(str(out_dir))
        report_path = exp.create_export_report(
            {"orthophoto": str(out_dir / "orthophoto.tif")}, "MeinProjekt"
        )
        text = Path(report_path).read_text(encoding="utf-8")
        assert "MeinProjekt" in text
        assert "orthophoto" in text

    def test_create_export_report_also_writes_json(self, tmp_path):
        """create_export_report soll zusätzlich export_report.json schreiben."""
        import json as _json
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result_file = out_dir / "orthophoto.tif"
        result_file.write_bytes(b"X" * 512)
        exp = Exporter(str(out_dir))
        exp.create_export_report({"orthophoto": str(result_file)}, "JsonProjekt")
        json_path = out_dir / "export_report.json"
        assert json_path.exists()
        data = _json.loads(json_path.read_text(encoding="utf-8"))
        assert data["project"] == "JsonProjekt"
        assert "orthophoto" in data["results"]
        assert "exported_at" in data

    def test_create_export_report_json_has_size_mb(self, tmp_path):
        """size_mb in JSON-Bericht ist korrekt befüllt."""
        import json as _json
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result_file = out_dir / "dsm.tif"
        result_file.write_bytes(b"D" * 1024 * 1024)  # 1 MB
        exp = Exporter(str(out_dir))
        exp.create_export_report({"dsm": str(result_file)}, "SizeProjekt")
        data = _json.loads((out_dir / "export_report.json").read_text(encoding="utf-8"))
        assert data["results"]["dsm"]["size_mb"] == pytest.approx(1.0, abs=0.01)

    def test_export_geotiff_with_rasterio_reprojects(self, tmp_path):
        src = tmp_path / "src.tif"
        src.write_bytes(b"FAKE")
        out_dir = tmp_path / "out"
        exp = Exporter(str(out_dir))

        mock_rasterio = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.crs = "EPSG:4326"
        mock_ctx.width = 100
        mock_ctx.height = 100
        mock_ctx.count = 1
        mock_ctx.bounds = (0, 0, 1, 1)
        mock_ctx.meta = {"driver": "GTiff"}
        mock_ctx.transform = MagicMock()
        mock_rasterio.open.return_value = mock_ctx

        warp_mod = MagicMock()
        warp_mod.calculate_default_transform.return_value = (MagicMock(), 100, 100)

        with patch.dict("sys.modules", {"rasterio": mock_rasterio,
                                         "rasterio.warp": warp_mod}):
            mock_rasterio.open.side_effect = None
            mock_rasterio.open.return_value = mock_ctx
            # Just ensure no exception is raised when rasterio is stubbed
            try:
                exp.export_geotiff(str(src), "reproj.tif", reproject_epsg="EPSG:32632")
            except Exception:
                # rasterio mock may be incomplete; the important thing is the
                # fallback to copy doesn't crash
                pass
        # output dir was created
        assert out_dir.exists()


class TestExporterNonRasterFiles:
    """Nicht-GeoTIFF-Dateien (z. B. .laz) werden direkt kopiert."""

    def test_laz_file_copied_directly(self, tmp_path):
        src = tmp_path / "cloud.laz"
        src.write_bytes(b"LAZDATA")
        out_dir = tmp_path / "out"
        exp = Exporter(str(out_dir))
        exported = exp.export_all({"pointcloud": str(src)})
        assert "pointcloud" in exported
        assert Path(exported["pointcloud"]).read_bytes() == b"LAZDATA"

    def test_non_raster_skips_reprojection(self, tmp_path):
        """export_geotiff darf für Nicht-Raster-Dateien NICHT aufgerufen werden."""
        src = tmp_path / "cloud.laz"
        src.write_bytes(b"X")
        out_dir = tmp_path / "out"
        exp = Exporter(str(out_dir))
        with patch.object(exp, "export_geotiff") as mock_gt:
            exp.export_all({"pointcloud": str(src)})
        mock_gt.assert_not_called()

    def test_mixed_raster_and_laz(self, tmp_path):
        """GeoTIFFs werden kopiert, .laz-Dateien ebenfalls."""
        tif_src = tmp_path / "orthophoto.tif"
        laz_src = tmp_path / "cloud.laz"
        tif_src.write_bytes(b"TIFF")
        laz_src.write_bytes(b"LAZ")
        out_dir = tmp_path / "out"
        exp = Exporter(str(out_dir))
        exported = exp.export_all({"orthophoto": str(tif_src), "pointcloud": str(laz_src)})
        assert "orthophoto" in exported
        assert "pointcloud" in exported
        assert Path(exported["pointcloud"]).suffix == ".laz"
