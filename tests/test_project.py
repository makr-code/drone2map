"""Tests für drone2map.core.project."""
import json
import pytest
from drone2map.core.project import Project, ProjectSettings


def test_project_defaults():
    p = Project(name="Test")
    assert p.image_count == 0
    assert p.status == "neu"
    assert p.is_ready is False


def test_add_images():
    p = Project(name="Test", output_dir="/tmp/out")
    added = p.add_images(["/a/1.jpg", "/a/2.jpg"])
    assert added == 2
    assert p.image_count == 2


def test_add_images_no_duplicates():
    p = Project(name="Test")
    p.add_images(["/a/1.jpg"])
    added = p.add_images(["/a/1.jpg", "/a/2.jpg"])
    assert added == 1
    assert p.image_count == 2


def test_remove_image():
    p = Project(name="Test")
    p.add_images(["/a/1.jpg"])
    assert p.remove_image("/a/1.jpg") is True
    assert p.image_count == 0


def test_remove_missing_image():
    p = Project(name="Test")
    assert p.remove_image("/nope.jpg") is False


def test_is_ready_needs_output_dir():
    p = Project(name="Test")
    p.add_images(["/1.jpg", "/2.jpg", "/3.jpg"])
    assert p.is_ready is False
    p.output_dir = "/tmp/out"
    assert p.is_ready is True


def test_set_result():
    p = Project(name="Test")
    p.set_result("orthophoto", "/out/ortho.tif")
    assert p.result_paths["orthophoto"] == "/out/ortho.tif"


def test_save_and_load(tmp_path):
    p = Project(name="SaveTest", output_dir=str(tmp_path))
    p.add_images(["/a/1.jpg", "/a/2.jpg"])
    p.settings.dsm = False
    path = p.save(tmp_path / "project.d2m.json")
    loaded = Project.load(path)
    assert loaded.name == "SaveTest"
    assert loaded.image_count == 2
    assert loaded.settings.dsm is False
    assert loaded.file_path == path


def test_save_raises_without_path():
    p = Project(name="Test")
    with pytest.raises(ValueError):
        p.save()
