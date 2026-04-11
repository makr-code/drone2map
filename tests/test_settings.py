"""Tests für drone2map.config.settings."""
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from drone2map.config.settings import AppSettings, OdmDefaults


class TestAppSettings:
    def test_defaults(self):
        s = AppSettings()
        assert s.theme == "darkly"
        assert s.last_project is None
        assert s.recent_projects == []
        assert s.odm.node_port == 3000
        assert s.odm.node_host == "localhost"

    def test_add_recent_prepends(self):
        s = AppSettings()
        s.add_recent("/path/a.json")
        s.add_recent("/path/b.json")
        assert s.recent_projects[0] == "/path/b.json"
        assert s.recent_projects[1] == "/path/a.json"

    def test_add_recent_deduplicates(self):
        s = AppSettings()
        s.add_recent("/path/a.json")
        s.add_recent("/path/b.json")
        s.add_recent("/path/a.json")
        assert s.recent_projects.count("/path/a.json") == 1
        assert s.recent_projects[0] == "/path/a.json"

    def test_add_recent_limits_to_10(self):
        s = AppSettings()
        for i in range(15):
            s.add_recent(f"/path/{i}.json")
        assert len(s.recent_projects) == 10

    def test_save_and_load(self, tmp_path):
        cfg = tmp_path / ".drone2map" / "settings.json"
        s = AppSettings()
        s.theme = "flatly"
        s.last_project = "/some/project.d2m.json"
        s.odm.node_port = 3001

        with patch("drone2map.config.settings._CFG", cfg):
            s.save()
            loaded = AppSettings.load()

        assert loaded.theme == "flatly"
        assert loaded.last_project == "/some/project.d2m.json"
        assert loaded.odm.node_port == 3001

    def test_load_returns_defaults_when_missing(self, tmp_path):
        nonexistent = tmp_path / "no_settings.json"
        with patch("drone2map.config.settings._CFG", nonexistent):
            s = AppSettings.load()
        assert s.theme == "darkly"

    def test_load_tolerates_corrupt_json(self, tmp_path):
        cfg = tmp_path / "bad.json"
        cfg.write_text("{bad json", encoding="utf-8")
        with patch("drone2map.config.settings._CFG", cfg):
            s = AppSettings.load()
        assert s.theme == "darkly"

    def test_load_ignores_unknown_keys(self, tmp_path):
        cfg = tmp_path / "settings.json"
        cfg.write_text(json.dumps({"theme": "solar", "unknown_key": 42}), encoding="utf-8")
        with patch("drone2map.config.settings._CFG", cfg):
            s = AppSettings.load()
        assert s.theme == "solar"

    def test_save_creates_parent_dir(self, tmp_path):
        cfg = tmp_path / "deep" / "nested" / "settings.json"
        s = AppSettings()
        with patch("drone2map.config.settings._CFG", cfg):
            s.save()
        assert cfg.exists()


class TestOdmDefaults:
    def test_default_max_retries(self):
        d = OdmDefaults()
        assert d.max_retries == 3

    def test_default_retry_delay(self):
        d = OdmDefaults()
        assert d.retry_delay == 5.0

    def test_custom_max_retries(self):
        d = OdmDefaults(max_retries=10)
        assert d.max_retries == 10

    def test_custom_retry_delay(self):
        d = OdmDefaults(retry_delay=30.0)
        assert d.retry_delay == 30.0

    def test_save_and_load_preserves_retry_fields(self, tmp_path):
        cfg = tmp_path / "settings.json"
        s = AppSettings()
        s.odm.max_retries = 7
        s.odm.retry_delay = 12.5
        with patch("drone2map.config.settings._CFG", cfg):
            s.save()
            loaded = AppSettings.load()
        assert loaded.odm.max_retries == 7
        assert loaded.odm.retry_delay == 12.5

    def test_load_older_settings_without_retry_fields_uses_defaults(self, tmp_path):
        """Ältere settings.json ohne retry-Felder laden mit Standardwerten."""
        cfg = tmp_path / "settings.json"
        old_data = {
            "theme": "cosmo",
            "last_project": None,
            "recent_projects": [],
            "output_dir": str(tmp_path),
            "odm": {
                "dsm": True,
                "dtm": False,
                "orthophoto_resolution": 5.0,
                "feature_quality": "medium",
                "pc_quality": "low",
                "mesh_octree_depth": 10,
                "node_host": "remotehost",
                "node_port": 3001,
            },
        }
        cfg.write_text(json.dumps(old_data), encoding="utf-8")
        with patch("drone2map.config.settings._CFG", cfg):
            loaded = AppSettings.load()
        assert loaded.odm.max_retries == 3
        assert loaded.odm.retry_delay == 5.0
        # existing fields still loaded correctly
        assert loaded.odm.node_host == "remotehost"
        assert loaded.odm.node_port == 3001
