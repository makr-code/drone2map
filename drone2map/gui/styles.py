"""Globale Stildefinitionen und Farben für die drone2map GUI."""
from __future__ import annotations

THEME = "darkly"

COLORS = {
    "primary": "#375a7f",
    "success": "#00bc8c",
    "warning": "#f39c12",
    "danger": "#e74c3c",
    "info": "#3498db",
    "light": "#adb5bd",
    "dark": "#303030",
    "bg": "#222222",
    "fg": "#ffffff",
}

FONTS = {
    "default": ("Segoe UI", 10),
    "bold": ("Segoe UI", 10, "bold"),
    "heading": ("Segoe UI", 13, "bold"),
    "mono": ("Consolas", 9),
    "small": ("Segoe UI", 9),
}

PADDING = {"xs": 2, "sm": 5, "md": 10, "lg": 20}

MAP_TILE_SERVERS = {
    "OpenStreetMap": "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "Satellite": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    "Terrain": "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
}
