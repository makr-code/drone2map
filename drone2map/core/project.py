"""Projektmanagement: JSON-basierte Projekte."""
from __future__ import annotations
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class ProjectSettings:
    dsm: bool = True
    dtm: bool = True
    orthophoto_resolution: float = 5.0
    feature_quality: str = "high"
    pc_quality: str = "high"
    mesh_octree_depth: int = 12
    node_host: str = "localhost"
    node_port: int = 3000

@dataclass
class Project:
    name: str
    image_paths: list[str] = field(default_factory=list)
    output_dir: str = ""
    settings: ProjectSettings = field(default_factory=ProjectSettings)
    status: str = "neu"
    result_paths: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    file_path: Optional[str] = None

    def save(self, path: Optional[str | Path] = None) -> str:
        p = Path(path) if path else (Path(self.file_path) if self.file_path else None)
        if p is None:
            raise ValueError("Kein Speicherpfad")
        self.updated_at = datetime.now().isoformat()
        p.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        data.pop("file_path", None)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        self.file_path = str(p)
        return str(p)

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        path = Path(path)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        sd = data.pop("settings", {})
        s = ProjectSettings(**{k: v for k, v in sd.items() if k in ProjectSettings.__dataclass_fields__})
        inst = cls(name=data.get("name", path.stem), settings=s,
                   image_paths=data.get("image_paths", []),
                   output_dir=data.get("output_dir", ""),
                   status=data.get("status", "neu"),
                   result_paths=data.get("result_paths", {}),
                   created_at=data.get("created_at", ""),
                   updated_at=data.get("updated_at", ""))
        inst.file_path = str(path)
        return inst

    def add_images(self, paths: list[str]) -> int:
        existing = set(self.image_paths)
        added = 0
        for p in paths:
            if p not in existing:
                self.image_paths.append(p)
                existing.add(p)
                added += 1
        return added

    def remove_image(self, path: str) -> bool:
        if path in self.image_paths:
            self.image_paths.remove(path)
            return True
        return False

    def set_result(self, key: str, path: str) -> None:
        self.result_paths[key] = path
        self.updated_at = datetime.now().isoformat()

    @property
    def image_count(self) -> int: return len(self.image_paths)
    @property
    def is_ready(self) -> bool: return len(self.image_paths) >= 3 and bool(self.output_dir)
