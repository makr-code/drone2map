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

    def test_add_recent_prepends(self, tmp_path):
        p_a = tmp_path / "a.json"
        p_b = tmp_path / "b.json"
        p_a.write_text("{}")
        p_b.write_text("{}")
        s = AppSettings()
        s.add_recent(str(p_a))
        s.add_recent(str(p_b))
        assert s.recent_projects[0] == str(p_b)
        assert s.recent_projects[1] == str(p_a)

    def test_add_recent_deduplicates(self, tmp_path):
        p_a = tmp_path / "a.json"
        p_b = tmp_path / "b.json"
        p_a.write_text("{}")
        p_b.write_text("{}")
        s = AppSettings()
        s.add_recent(str(p_a))
        s.add_recent(str(p_b))
        s.add_recent(str(p_a))
        assert s.recent_projects.count(str(p_a)) == 1
        assert s.recent_projects[0] == str(p_a)

    def test_add_recent_limits_to_10(self, tmp_path):
        s = AppSettings()
        for i in range(15):
            p = tmp_path / f"{i}.json"
            p.write_text("{}")
            s.add_recent(str(p))
        assert len(s.recent_projects) == 10

    def test_add_recent_prunes_nonexistent_paths(self, tmp_path):
        """Pfade, die nicht mehr auf der Disk existieren, werden entfernt."""
        s = AppSettings()
        real = tmp_path / "real.json"
        real.write_text("{}")
        ghost = tmp_path / "ghost.json"
        ghost.write_text("{}")
        s.add_recent(str(real))
        s.add_recent(str(ghost))
        ghost.unlink()  # simulate deleted file
        # Adding any path triggers pruning
        real2 = tmp_path / "real2.json"
        real2.write_text("{}")
        s.add_recent(str(real2))
        assert str(ghost) not in s.recent_projects

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

    def test_default_log_level(self):
        s = AppSettings()
        assert s.log_level == "INFO"

    def test_save_and_load_preserves_log_level(self, tmp_path):
        cfg = tmp_path / "settings.json"
        s = AppSettings()
        s.log_level = "DEBUG"
        with patch("drone2map.config.settings._CFG", cfg):
            s.save()
            loaded = AppSettings.load()
        assert loaded.log_level == "DEBUG"

    def test_load_older_settings_without_log_level_uses_default(self, tmp_path):
        """Ältere settings.json ohne log_level laden mit Standardwert INFO."""
        cfg = tmp_path / "settings.json"
        old_data = {"theme": "solar", "output_dir": str(tmp_path)}
        cfg.write_text(json.dumps(old_data), encoding="utf-8")
        with patch("drone2map.config.settings._CFG", cfg):
            loaded = AppSettings.load()
        assert loaded.log_level == "INFO"
