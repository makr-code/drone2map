"""Bildvalidierung."""
from __future__ import annotations
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from .exif_parser import ExifParser, ImageMetadata, SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)
MIN_IMAGE_COUNT = 3

@dataclass
class ValidationResult:
    file_path: str
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: Optional[ImageMetadata] = None

    @property
    def filename(self) -> str: return Path(self.file_path).name

class ImageValidator:
    def __init__(self, require_gps: bool = True, max_size_mb: float = 500):
        self.require_gps = require_gps
        self.max_size_mb = max_size_mb
        self._parser = ExifParser()

    def validate_file(self, path: str | Path) -> ValidationResult:
        path = Path(path)
        r = ValidationResult(file_path=str(path))
        if not path.exists():
            r.valid = False
            r.errors.append("Datei nicht gefunden")
            return r
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            r.valid = False
            r.errors.append(f"Unsupported: {path.suffix}")
            return r
        if path.stat().st_size / 1_048_576 > self.max_size_mb:
            r.warnings.append(f"Große Datei: {path.stat().st_size/1_048_576:.1f} MB")
        try:
            meta = self._parser.parse_file(path)
            r.metadata = meta
        except Exception as exc:
            r.valid = False
            r.errors.append(f"EXIF-Fehler: {exc}")
            return r
        if self.require_gps and not meta.gps_valid:
            r.valid = False
            r.errors.append("Keine GPS-Koordinaten")
        return r

    def validate_batch(self, paths: list[str | Path]) -> list[ValidationResult]:
        if not paths:
            return []
        max_workers = min(os.cpu_count() or 1, len(paths))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            return list(executor.map(self.validate_file, paths))

    def validate_folder(self, folder: str | Path) -> list[ValidationResult]:
        folder = Path(folder)
        files = sorted([
            f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        ])
        return self.validate_batch(files)

    @staticmethod
    def check_minimum_count(results: list[ValidationResult]) -> bool:
        return sum(1 for r in results if r.valid) >= MIN_IMAGE_COUNT
