"""Tests für drone2map.core.exif_parser."""
import io
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from drone2map.core.exif_parser import ExifParser, ImageMetadata, _dms_to_decimal, SUPPORTED_EXTENSIONS


def test_supported_extensions_set():
    assert ".jpg" in SUPPORTED_EXTENSIONS
    assert ".tif" in SUPPORTED_EXTENSIONS


def test_dms_to_decimal_north():
    class R:
        def __init__(self, n, d): self.num = n; self.den = d
    vals = [R(52, 1), R(30, 1), R(0, 1)]
    result = _dms_to_decimal(vals, "N")
    assert abs(result - 52.5) < 1e-9


def test_dms_to_decimal_south():
    class R:
        def __init__(self, n, d): self.num = n; self.den = d
    vals = [R(10, 1), R(0, 1), R(0, 1)]
    result = _dms_to_decimal(vals, "S")
    assert result == -10.0


def test_dms_to_decimal_west():
    class R:
        def __init__(self, n, d): self.num = n; self.den = d
    vals = [R(7, 1), R(0, 1), R(0, 1)]
    result = _dms_to_decimal(vals, "W")
    assert result == -7.0


def test_image_metadata_filename():
    meta = ImageMetadata(file_path="/some/path/image.jpg")
    assert meta.filename == "image.jpg"


def test_parse_file_missing():
    parser = ExifParser()
    meta = parser.parse_file("/nonexistent/path/image.jpg")
    assert meta.gps_valid is False
    assert meta.filename == "image.jpg"


def test_parse_folder_empty(tmp_path):
    parser = ExifParser()
    result = parser.parse_folder(tmp_path)
    assert result == []


def test_parse_folder_filters_unsupported(tmp_path):
    (tmp_path / "doc.txt").write_text("hello")
    (tmp_path / "image.jpg").write_bytes(b"\xff\xd8\xff")  # minimal JPEG header
    parser = ExifParser()
    result = parser.parse_folder(tmp_path)
    assert len(result) == 1
    assert result[0].filename == "image.jpg"
