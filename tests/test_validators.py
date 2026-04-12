"""Tests für drone2map.core.validators."""
from pathlib import Path
import pytest
from drone2map.core.validators import ImageValidator, ValidationResult, MIN_IMAGE_COUNT


def test_validate_missing_file():
    v = ImageValidator()
    r = v.validate_file("/nonexistent/image.jpg")
    assert r.valid is False
    assert "nicht gefunden" in r.errors[0]


def test_validate_unsupported_extension(tmp_path):
    f = tmp_path / "file.bmp"
    f.write_bytes(b"BM")
    v = ImageValidator()
    r = v.validate_file(f)
    assert r.valid is False


def test_validate_batch_empty():
    v = ImageValidator()
    results = v.validate_batch([])
    assert results == []


def test_check_minimum_count_false():
    results = [ValidationResult(file_path=f"/img{i}.jpg", valid=True) for i in range(2)]
    assert ImageValidator.check_minimum_count(results) is False


def test_check_minimum_count_true():
    results = [ValidationResult(file_path=f"/img{i}.jpg", valid=True) for i in range(MIN_IMAGE_COUNT)]
    assert ImageValidator.check_minimum_count(results) is True


def test_check_minimum_count_mixed():
    results = [ValidationResult(file_path=f"/img{i}.jpg", valid=True) for i in range(MIN_IMAGE_COUNT)]
    results.append(ValidationResult(file_path="/bad.jpg", valid=False))
    assert ImageValidator.check_minimum_count(results) is True


def test_validate_folder_empty(tmp_path):
    v = ImageValidator()
    results = v.validate_folder(tmp_path)
    assert results == []


def test_validate_folder_counts_files(tmp_path):
    for name in ["a.jpg", "b.tif", "c.txt"]:
        (tmp_path / name).write_bytes(b"\x00")
    v = ImageValidator(require_gps=False)
    results = v.validate_folder(tmp_path)
    # txt should be excluded
    assert len(results) == 2


def test_validation_result_filename():
    r = ValidationResult(file_path="/some/path/photo.jpg")
    assert r.filename == "photo.jpg"


def test_validate_file_require_gps_false_is_valid(tmp_path):
    """require_gps=False: Datei ohne GPS soll trotzdem valid sein."""
    f = tmp_path / "image.jpg"
    f.write_bytes(b"\xff\xd8\xff")
    v = ImageValidator(require_gps=False)
    r = v.validate_file(f)
    assert "Keine GPS-Koordinaten" not in r.errors


def test_validate_file_require_gps_true_invalid_without_gps(tmp_path):
    """require_gps=True (default): Datei ohne GPS-EXIF soll invalid sein."""
    f = tmp_path / "image.jpg"
    f.write_bytes(b"\xff\xd8\xff")
    v = ImageValidator(require_gps=True)
    r = v.validate_file(f)
    assert r.valid is False
    assert any("GPS" in e for e in r.errors)


def test_validation_result_no_errors_by_default():
    r = ValidationResult(file_path="/img.jpg")
    assert r.valid is True
    assert r.errors == []
    assert r.warnings == []


def test_validate_batch_returns_all(tmp_path):
    files = []
    for name in ["a.jpg", "b.jpg"]:
        f = tmp_path / name
        f.write_bytes(b"\xff\xd8\xff")
        files.append(str(f))
    v = ImageValidator(require_gps=False)
    results = v.validate_batch(files)
    assert len(results) == 2


def test_validate_batch_preserves_order(tmp_path):
    """validate_batch soll die Reihenfolge der Eingabepfade erhalten."""
    files = []
    for i in range(10):
        f = tmp_path / f"img_{i:02d}.jpg"
        f.write_bytes(b"\xff\xd8\xff")
        files.append(str(f))
    v = ImageValidator(require_gps=False)
    results = v.validate_batch(files)
    for i, r in enumerate(results):
        assert r.file_path == files[i]


def test_validate_batch_parallel_large(tmp_path):
    """Parallele Validierung mit vielen Dateien darf keinen Fehler werfen."""
    files = []
    for i in range(20):
        f = tmp_path / f"img_{i}.jpg"
        f.write_bytes(b"\xff\xd8\xff")
        files.append(str(f))
    v = ImageValidator(require_gps=False)
    results = v.validate_batch(files)
    assert len(results) == 20
