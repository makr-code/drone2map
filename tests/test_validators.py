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
