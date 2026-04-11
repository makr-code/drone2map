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


def test_dms_to_decimal_east():
    class R:
        def __init__(self, n, d): self.num = n; self.den = d
    vals = [R(13, 1), R(24, 1), R(0, 1)]
    result = _dms_to_decimal(vals, "E")
    assert abs(result - 13.4) < 1e-9


def test_image_metadata_filename():
    meta = ImageMetadata(file_path="/some/path/image.jpg")
    assert meta.filename == "image.jpg"


def test_image_metadata_has_valid_coordinates_false_by_default():
    meta = ImageMetadata(file_path="/img.jpg")
    assert meta.has_valid_coordinates is False


def test_image_metadata_has_valid_coordinates_needs_gps_flag():
    meta = ImageMetadata(file_path="/img.jpg", latitude=52.0, longitude=13.0, gps_valid=False)
    assert meta.has_valid_coordinates is False


def test_image_metadata_has_valid_coordinates_needs_both_coords():
    meta = ImageMetadata(file_path="/img.jpg", latitude=52.0, gps_valid=True)
    assert meta.has_valid_coordinates is False


def test_image_metadata_has_valid_coordinates_true():
    meta = ImageMetadata(file_path="/img.jpg", latitude=52.0, longitude=13.0, gps_valid=True)
    assert meta.has_valid_coordinates is True


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


def test_parse_folder_sorted_order(tmp_path):
    for name in ["c.jpg", "a.jpg", "b.jpg"]:
        (tmp_path / name).write_bytes(b"\xff\xd8\xff")
    parser = ExifParser()
    result = parser.parse_folder(tmp_path)
    names = [r.filename for r in result]
    assert names == sorted(names)


def test_parse_file_pillow_fallback_no_gps(tmp_path):
    """Pillow-Fallback: Datei ohne GPS liefert gps_valid=False."""
    img_file = tmp_path / "test.jpg"
    img_file.write_bytes(b"\xff\xd8\xff")  # minimal header

    mock_img = MagicMock()
    mock_img.size = (4000, 3000)
    mock_img._getexif.return_value = {
        271: "DJI",    # Make
        272: "FC3411", # Model
    }

    mock_pil = MagicMock()
    mock_pil.Image.open.return_value.__enter__ = lambda s: mock_img
    mock_pil.Image.open.return_value = mock_img
    mock_pil.ExifTags.TAGS = {271: "Make", 272: "Model"}
    mock_pil.ExifTags.GPSTAGS = {}

    import sys
    with patch.dict(sys.modules, {"exifread": None}):
        with patch.dict(sys.modules, {"PIL": mock_pil, "PIL.Image": mock_pil.Image,
                                       "PIL.ExifTags": mock_pil.ExifTags}):
            parser = ExifParser()
            meta = parser.parse_file(img_file)

    assert meta.gps_valid is False
    assert meta.filename == "test.jpg"


class TestPillowFallbackExtraFields:
    """Tests für die erweiterten Felder in ExifParser._from_pillow."""

    def _make_mock_pil(self, exif_dict, gps_dict=None):
        """Erzeugt ein minimales PIL-Mock mit den angegebenen EXIF-Tags."""
        from fractions import Fraction

        make_tag_map = {
            271: "Make", 272: "Model", 306: "DateTimeOriginal",
            37386: "FocalLength", 34855: "ISOSpeedRatings", 33434: "ExposureTime",
            34853: "GPSInfo",
        }
        gps_tag_map = {
            1: "GPSLatitudeRef", 2: "GPSLatitude",
            3: "GPSLongitudeRef", 4: "GPSLongitude",
            6: "GPSAltitude",
        }

        mock_img = MagicMock()
        mock_img.size = (4000, 3000)
        if gps_dict is not None:
            exif_dict[34853] = gps_dict
        mock_img._getexif.return_value = exif_dict

        mock_pil = MagicMock()
        mock_pil.Image.open.return_value = mock_img
        mock_pil.ExifTags.TAGS = make_tag_map
        mock_pil.ExifTags.GPSTAGS = gps_tag_map
        return mock_pil

    def _parse_with_pillow(self, mock_pil, tmp_path):
        import sys
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"\xff\xd8\xff")
        with patch.dict(sys.modules, {"exifread": None}):
            with patch.dict(sys.modules, {"PIL": mock_pil, "PIL.Image": mock_pil.Image,
                                           "PIL.ExifTags": mock_pil.ExifTags}):
                parser = ExifParser()
                return parser.parse_file(img_file)

    def test_focal_length_extracted(self, tmp_path):
        from fractions import Fraction
        fl = MagicMock()
        fl.numerator = 240
        fl.denominator = 10
        mock_pil = self._make_mock_pil({271: "DJI", 272: "FC3411", 37386: fl})
        meta = self._parse_with_pillow(mock_pil, tmp_path)
        assert meta.focal_length == pytest.approx(24.0)

    def test_iso_extracted(self, tmp_path):
        mock_pil = self._make_mock_pil({271: "DJI", 272: "FC3411", 34855: 100})
        meta = self._parse_with_pillow(mock_pil, tmp_path)
        assert meta.iso == 100

    def test_exposure_time_extracted(self, tmp_path):
        et = MagicMock()
        et.numerator = 1
        et.denominator = 500
        mock_pil = self._make_mock_pil({271: "DJI", 272: "FC3411", 33434: et})
        meta = self._parse_with_pillow(mock_pil, tmp_path)
        assert meta.exposure_time == "1/500"

    def test_gps_altitude_extracted(self, tmp_path):
        from fractions import Fraction
        lat_rat = [MagicMock(numerator=52, denominator=1),
                   MagicMock(numerator=0, denominator=1),
                   MagicMock(numerator=0, denominator=1)]
        lon_rat = [MagicMock(numerator=13, denominator=1),
                   MagicMock(numerator=0, denominator=1),
                   MagicMock(numerator=0, denominator=1)]
        alt = MagicMock()
        alt.numerator = 1200
        alt.denominator = 10
        gps = {1: "N", 2: lat_rat, 3: "E", 4: lon_rat, 6: alt}
        mock_pil = self._make_mock_pil({271: "DJI"}, gps_dict=gps)
        meta = self._parse_with_pillow(mock_pil, tmp_path)
        assert meta.altitude == pytest.approx(120.0)
        assert meta.gps_valid is True
