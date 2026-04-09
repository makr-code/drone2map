"""Tests für drone2map.core.geo_utils."""
import math
import pytest
from drone2map.core.geo_utils import GeoUtils


def test_haversine_same_point():
    d = GeoUtils.haversine_distance(52.0, 13.0, 52.0, 13.0)
    assert d == 0.0


def test_haversine_known_distance():
    # Berlin -> Hamburg ca. 255 km
    d = GeoUtils.haversine_distance(52.52, 13.405, 53.55, 10.0)
    assert 240_000 < d < 270_000


def test_bounding_box_none_on_empty():
    assert GeoUtils.bounding_box([], []) is None


def test_bounding_box_values():
    bb = GeoUtils.bounding_box([1.0, 3.0, 2.0], [10.0, 12.0, 11.0])
    assert bb == (1.0, 10.0, 3.0, 12.0)


def test_best_utm_epsg_northern():
    epsg = GeoUtils.best_utm_epsg([52.0], [13.0])
    assert epsg == "EPSG:32633"


def test_best_utm_epsg_southern():
    epsg = GeoUtils.best_utm_epsg([-10.0], [25.0])
    assert epsg.startswith("EPSG:327")


def test_best_utm_epsg_empty():
    epsg = GeoUtils.best_utm_epsg([], [])
    assert epsg == "EPSG:32632"


def test_calculate_gsd_zero_focal():
    assert GeoUtils.calculate_gsd(100, 0, 23.5, 4000) == 0.0


def test_calculate_gsd_positive():
    gsd = GeoUtils.calculate_gsd(100, 24.0, 23.5, 4000)
    assert gsd > 0


def test_wgs84_to_utm_returns_epsg():
    _, _, epsg = GeoUtils.wgs84_to_utm(52.0, 13.0)
    assert epsg.startswith("EPSG:")
