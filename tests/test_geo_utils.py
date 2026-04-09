"""Tests für drone2map.core.geo_utils."""
import math
import sys
from unittest.mock import patch
import pytest
from drone2map.core.geo_utils import GeoUtils


def test_haversine_same_point():
    d = GeoUtils.haversine_distance(52.0, 13.0, 52.0, 13.0)
    assert d == 0.0


def test_haversine_known_distance():
    # Berlin -> Hamburg ca. 255 km
    d = GeoUtils.haversine_distance(52.52, 13.405, 53.55, 10.0)
    assert 240_000 < d < 270_000


def test_haversine_equator_crossing():
    d = GeoUtils.haversine_distance(-1.0, 36.0, 1.0, 36.0)
    assert d > 0


def test_bounding_box_none_on_empty():
    assert GeoUtils.bounding_box([], []) is None


def test_bounding_box_values():
    bb = GeoUtils.bounding_box([1.0, 3.0, 2.0], [10.0, 12.0, 11.0])
    assert bb == (1.0, 10.0, 3.0, 12.0)


def test_bounding_box_single_point():
    bb = GeoUtils.bounding_box([52.0], [13.0])
    assert bb == (52.0, 13.0, 52.0, 13.0)


def test_best_utm_epsg_northern():
    epsg = GeoUtils.best_utm_epsg([52.0], [13.0])
    assert epsg == "EPSG:32633"


def test_best_utm_epsg_southern():
    epsg = GeoUtils.best_utm_epsg([-10.0], [25.0])
    assert epsg.startswith("EPSG:327")


def test_best_utm_epsg_empty():
    epsg = GeoUtils.best_utm_epsg([], [])
    assert epsg == "EPSG:32632"


def test_best_utm_epsg_multiple_points():
    epsg = GeoUtils.best_utm_epsg([48.1, 48.2], [11.5, 11.6])
    assert epsg.startswith("EPSG:326")


def test_calculate_gsd_zero_focal():
    assert GeoUtils.calculate_gsd(100, 0, 23.5, 4000) == 0.0


def test_calculate_gsd_zero_img_width():
    assert GeoUtils.calculate_gsd(100, 24.0, 23.5, 0) == 0.0


def test_calculate_gsd_positive():
    gsd = GeoUtils.calculate_gsd(100, 24.0, 23.5, 4000)
    assert gsd > 0


def test_calculate_gsd_higher_altitude_larger_gsd():
    gsd_low = GeoUtils.calculate_gsd(50, 24.0, 23.5, 4000)
    gsd_high = GeoUtils.calculate_gsd(150, 24.0, 23.5, 4000)
    assert gsd_high > gsd_low


def test_wgs84_to_utm_returns_epsg():
    _, _, epsg = GeoUtils.wgs84_to_utm(52.0, 13.0)
    assert epsg.startswith("EPSG:")


def test_wgs84_to_utm_northern_epsg():
    _, _, epsg = GeoUtils.wgs84_to_utm(52.0, 13.0)
    assert epsg == "EPSG:32633"


def test_wgs84_to_utm_southern_epsg():
    _, _, epsg = GeoUtils.wgs84_to_utm(-33.9, 18.4)
    assert epsg.startswith("EPSG:327")


def test_wgs84_to_utm_fallback_without_pyproj():
    """Ohne pyproj werden lon/lat unverändert zurückgegeben."""
    with patch.dict(sys.modules, {"pyproj": None}):
        e, n, epsg = GeoUtils.wgs84_to_utm(52.0, 13.0)
    assert e == 13.0
    assert n == 52.0
    assert epsg.startswith("EPSG:")


def test_utm_to_wgs84_fallback_without_pyproj():
    """Ohne pyproj werden northing, easting als lat, lon zurückgegeben."""
    with patch.dict(sys.modules, {"pyproj": None}):
        lat, lon = GeoUtils.utm_to_wgs84(391000.0, 5820000.0, "EPSG:32633")
    assert lat == 5820000.0
    assert lon == 391000.0
