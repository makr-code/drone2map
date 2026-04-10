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


class TestProjectSettingsRetry:
    def test_default_max_retries(self):
        s = ProjectSettings()
        assert s.max_retries == 3

    def test_default_retry_delay(self):
        s = ProjectSettings()
        assert s.retry_delay == 5.0

    def test_custom_max_retries(self):
        s = ProjectSettings(max_retries=10)
        assert s.max_retries == 10

    def test_custom_retry_delay(self):
        s = ProjectSettings(retry_delay=30.0)
        assert s.retry_delay == 30.0

    def test_save_and_load_preserves_retry_settings(self, tmp_path):
        p = Project(name="RetryTest", output_dir=str(tmp_path))
        p.settings.max_retries = 7
        p.settings.retry_delay = 12.5
        path = p.save(tmp_path / "retry.d2m.json")
        loaded = Project.load(path)
        assert loaded.settings.max_retries == 7
        assert loaded.settings.retry_delay == 12.5

    def test_load_older_project_without_retry_fields_uses_defaults(self, tmp_path):
        """Projekte ohne retry-Felder (ältere Versionen) laden mit Standardwerten."""
        import json
        old_project = {
            "name": "OldProject",
            "output_dir": str(tmp_path),
            "image_paths": [],
            "settings": {
                "dsm": True,
                "dtm": False,
                "orthophoto_resolution": 5.0,
                "feature_quality": "medium",
                "pc_quality": "medium",
                "mesh_octree_depth": 10,
                "node_host": "localhost",
                "node_port": 3000,
            },
            "status": "neu",
            "result_paths": {},
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }
        p_file = tmp_path / "old.d2m.json"
        p_file.write_text(json.dumps(old_project), encoding="utf-8")
        loaded = Project.load(p_file)
        assert loaded.settings.max_retries == 3
        assert loaded.settings.retry_delay == 5.0
