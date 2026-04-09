"""Koordinatentransformationen und Geo-Berechnungen."""
from __future__ import annotations
import logging, math
from typing import Optional

logger = logging.getLogger(__name__)


class GeoUtils:
    """Sammlung statischer Geo-Hilfsmethoden (Namespace-Klasse).

    Alle Methoden sind ``@staticmethod`` ohne Zustand. Die Klasse dient
    ausschließlich als Namensraum; es werden keine Instanzen benötigt.
    Aufrufe erfolgen direkt über die Klasse: ``GeoUtils.haversine_distance(...)``.
    """
    @staticmethod
    def wgs84_to_utm(lat: float, lon: float) -> tuple[float, float, str]:
        zone = int((lon + 180) / 6) + 1
        epsg = 32600 + zone if lat >= 0 else 32700 + zone
        try:
            import pyproj
            t = pyproj.Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
            e, n = t.transform(lon, lat)
            return e, n, f"EPSG:{epsg}"
        except ImportError:
            return lon, lat, f"EPSG:{epsg}"

    @staticmethod
    def utm_to_wgs84(easting: float, northing: float, epsg: str) -> tuple[float, float]:
        try:
            import pyproj
            t = pyproj.Transformer.from_crs(epsg, "EPSG:4326", always_xy=True)
            lon, lat = t.transform(easting, northing)
            return lat, lon
        except ImportError:
            return northing, easting

    @staticmethod
    def best_utm_epsg(lats: list[float], lons: list[float]) -> str:
        if not lats:
            return "EPSG:32632"
        ml, mn = sum(lats)/len(lats), sum(lons)/len(lons)
        zone = int((mn + 180) / 6) + 1
        return f"EPSG:{32600 + zone if ml >= 0 else 32700 + zone}"

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6_371_000.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
        a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        return 2*R*math.atan2(math.sqrt(a), math.sqrt(1-a))

    @staticmethod
    def bounding_box(lats: list[float], lons: list[float]) -> Optional[tuple[float,float,float,float]]:
        if not lats:
            return None
        return min(lats), min(lons), max(lats), max(lons)

    @staticmethod
    def calculate_gsd(altitude_m: float, focal_mm: float, sensor_w_mm: float, img_w_px: int) -> float:
        if focal_mm <= 0 or img_w_px <= 0:
            return 0.0
        return (altitude_m * sensor_w_mm * 100.0) / (focal_mm * img_w_px)
