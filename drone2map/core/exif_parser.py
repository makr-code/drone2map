"""EXIF/GPS-Metadaten-Extraktion aus Drohnenbildern."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}

@dataclass
class ImageMetadata:
    file_path: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    camera_model: str = ""
    camera_make: str = ""
    focal_length: Optional[float] = None
    datetime_original: str = ""
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    iso: Optional[int] = None
    exposure_time: str = ""
    gps_valid: bool = False
    raw_tags: dict = field(default_factory=dict, repr=False)

    @property
    def filename(self) -> str:
        return Path(self.file_path).name

    @property
    def has_valid_coordinates(self) -> bool:
        """True wenn GPS-Flag gesetzt und beide Koordinaten vorhanden sind."""
        return self.gps_valid and self.latitude is not None and self.longitude is not None


def _dms_to_decimal(values: list, ref: str) -> float:
    def to_f(v):
        if hasattr(v, "num") and hasattr(v, "den") and v.den:
            return float(v.num) / float(v.den)
        return float(v)
    d, m, s = to_f(values[0]), to_f(values[1]), to_f(values[2])
    dec = d + m / 60.0 + s / 3600.0
    return -dec if ref.upper() in ("S", "W") else dec


class ExifParser:
    def parse_file(self, path: str | Path) -> ImageMetadata:
        path = Path(path)
        meta = ImageMetadata(file_path=str(path))
        try:
            import exifread
            with open(path, "rb") as fh:
                tags = exifread.process_file(fh, details=False)
            meta.raw_tags = {str(k): str(v) for k, v in tags.items()}
            self._from_exifread(meta, tags)
        except ImportError:
            self._from_pillow(meta, path)
        except Exception as exc:
            logger.warning("EXIF-Fehler %s: %s", path.name, exc)
        return meta

    def _from_exifread(self, meta: ImageMetadata, tags: dict) -> None:
        try:
            meta.latitude = _dms_to_decimal(tags["GPS GPSLatitude"].values, str(tags["GPS GPSLatitudeRef"]))
            meta.longitude = _dms_to_decimal(tags["GPS GPSLongitude"].values, str(tags["GPS GPSLongitudeRef"]))
            meta.gps_valid = True
        except KeyError:
            pass
        try:
            v = tags["GPS GPSAltitude"].values[0]
            meta.altitude = float(v.num) / float(v.den)
        except (KeyError, ZeroDivisionError):
            pass
        for tag, attr in [("Image Make", "camera_make"), ("Image Model", "camera_model"),
                           ("EXIF DateTimeOriginal", "datetime_original")]:
            if tag in tags:
                setattr(meta, attr, str(tags[tag]))
        if "EXIF FocalLength" in tags:
            v = tags["EXIF FocalLength"].values[0]
            try:
                meta.focal_length = float(v.num) / float(v.den)
            except (AttributeError, ZeroDivisionError):
                pass
        for tag, attr in [("EXIF ExifImageWidth", "image_width"),
                           ("EXIF ExifImageLength", "image_height"),
                           ("EXIF ISOSpeedRatings", "iso")]:
            if tag in tags:
                try:
                    setattr(meta, attr, int(str(tags[tag])))
                except ValueError:
                    pass
        if "EXIF ExposureTime" in tags:
            meta.exposure_time = str(tags["EXIF ExposureTime"])

    def _from_pillow(self, meta: ImageMetadata, path: Path) -> None:
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS
            img = Image.open(path)
            raw = img._getexif()
            if not raw:
                return
            d = {TAGS.get(k, k): v for k, v in raw.items()}
            meta.camera_make = str(d.get("Make", ""))
            meta.camera_model = str(d.get("Model", ""))
            meta.datetime_original = str(d.get("DateTimeOriginal", ""))
            meta.image_width, meta.image_height = img.size
            if "FocalLength" in d:
                try:
                    fl = d["FocalLength"]
                    meta.focal_length = fl.numerator / fl.denominator
                except (AttributeError, ZeroDivisionError):
                    pass
            if "ISOSpeedRatings" in d:
                try:
                    meta.iso = int(d["ISOSpeedRatings"])
                except (TypeError, ValueError):
                    pass
            if "ExposureTime" in d:
                try:
                    et = d["ExposureTime"]
                    meta.exposure_time = f"{et.numerator}/{et.denominator}"
                except AttributeError:
                    meta.exposure_time = str(d["ExposureTime"])
            gps = d.get("GPSInfo")
            if gps:
                g = {GPSTAGS.get(k, k): v for k, v in gps.items()}
                try:
                    def rat(x): return x.numerator / x.denominator
                    lat = [rat(x) for x in g["GPSLatitude"]]
                    lon = [rat(x) for x in g["GPSLongitude"]]
                    meta.latitude = _dms_to_decimal(lat, str(g["GPSLatitudeRef"]))
                    meta.longitude = _dms_to_decimal(lon, str(g["GPSLongitudeRef"]))
                    meta.gps_valid = True
                except (KeyError, ZeroDivisionError):
                    pass
                if "GPSAltitude" in g:
                    try:
                        alt = g["GPSAltitude"]
                        meta.altitude = alt.numerator / alt.denominator
                    except (AttributeError, ZeroDivisionError):
                        pass
        except Exception as exc:
            logger.warning("Pillow EXIF %s: %s", path.name, exc)

    def parse_folder(self, folder: str | Path) -> list[ImageMetadata]:
        folder = Path(folder)
        files = sorted(
            [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS],
            key=lambda f: f.name,
        )
        return [self.parse_file(f) for f in files]
