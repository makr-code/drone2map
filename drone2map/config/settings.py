"""Persistente App-Einstellungen (JSON)."""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
_CFG = Path.home() / ".drone2map" / "settings.json"

@dataclass
class OdmDefaults:
    dsm: bool = True
    dtm: bool = True
    orthophoto_resolution: float = 5.0
    feature_quality: str = "high"
    pc_quality: str = "high"
    mesh_octree_depth: int = 12
    node_host: str = "localhost"
    node_port: int = 3000
    max_retries: int = 3
    retry_delay: float = 5.0

@dataclass
class AppSettings:
    theme: str = "darkly"
    last_project: Optional[str] = None
    recent_projects: list[str] = field(default_factory=list)
    output_dir: str = str(Path.home() / "drone2map_output")
    odm: OdmDefaults = field(default_factory=OdmDefaults)

    @classmethod
    def load(cls) -> "AppSettings":
        if not _CFG.exists():
            return cls()
        try:
            with open(_CFG, encoding="utf-8") as fh:
                data = json.load(fh)
            odm_data = data.pop("odm", {})
            inst = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            for k, v in odm_data.items():
                if k in OdmDefaults.__dataclass_fields__:
                    setattr(inst.odm, k, v)
            return inst
        except Exception as exc:
            logger.warning("Einstellungen nicht geladen: %s", exc)
            return cls()

    def save(self) -> None:
        _CFG.parent.mkdir(parents=True, exist_ok=True)
        with open(_CFG, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2, ensure_ascii=False)

    def add_recent(self, path: str) -> None:
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        # Keep only the 10 most-recent entries that still exist on disk
        self.recent_projects = [
            p for p in self.recent_projects[:20]
            if Path(p).exists()
        ][:10]
