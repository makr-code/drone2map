"""Widget: Interaktive Karte mit Bildpositionen."""
from __future__ import annotations
import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional
from ...core.exif_parser import ImageMetadata
from ..styles import MAP_TILE_SERVERS

logger = logging.getLogger(__name__)


class MapViewWidget(ttk.Frame):
    """Zeigt GPS-Punkte der Bilder auf einer interaktiven Karte (tkintermapview)."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._markers: list = []
        self._map_widget = None
        self._build()

    def _build(self) -> None:
        # Toolbar: Tile-Server-Auswahl
        toolbar = ttk.Frame(self)
        toolbar.pack(side="top", fill="x")
        ttk.Label(toolbar, text="Kartenlayer:").pack(side="left", padx=(4, 2))
        self._tile_var = tk.StringVar(value=list(MAP_TILE_SERVERS)[0])
        cb = ttk.Combobox(toolbar, textvariable=self._tile_var,
                          values=list(MAP_TILE_SERVERS.keys()),
                          state="readonly", width=14)
        cb.pack(side="left", padx=(0, 4))
        cb.bind("<<ComboboxSelected>>", self._on_tile_server_change)

        try:
            import tkintermapview  # type: ignore
            self._map_widget = tkintermapview.TkinterMapView(self, width=600, height=400, corner_radius=0)
            self._map_widget.pack(fill="both", expand=True)
            self._map_widget.set_tile_server(MAP_TILE_SERVERS[self._tile_var.get()])
        except ImportError:
            lbl = ttk.Label(self, text="tkintermapview nicht installiert.\nKarte nicht verfügbar.",
                            justify="center", anchor="center")
            lbl.pack(fill="both", expand=True)
            logger.warning("tkintermapview nicht verfügbar")

    def _on_tile_server_change(self, _event=None) -> None:
        """Wechselt den Karten-Tile-Server."""
        if self._map_widget is None:
            return
        url = MAP_TILE_SERVERS.get(self._tile_var.get())
        if url:
            self._map_widget.set_tile_server(url)

    def set_images(self, images: list[ImageMetadata]) -> None:
        """Platziert Marker für alle Bilder mit GPS-Daten."""
        if self._map_widget is None:
            return
        for m in self._markers:
            m.delete()
        self._markers.clear()

        gps_images = [img for img in images if img.has_valid_coordinates]
        if not gps_images:
            return

        for img in gps_images:
            marker = self._map_widget.set_marker(
                img.latitude, img.longitude,
                text=img.filename,
                marker_color_circle="#00bc8c",
                marker_color_outside="#375a7f",
            )
            self._markers.append(marker)

        lats = [img.latitude for img in gps_images]
        lons = [img.longitude for img in gps_images]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        self._map_widget.set_position(center_lat, center_lon)
        self._map_widget.set_zoom(16)

    def center_on(self, lat: float, lon: float, zoom: int = 17) -> None:
        if self._map_widget:
            self._map_widget.set_position(lat, lon)
            self._map_widget.set_zoom(zoom)

    def clear(self) -> None:
        if self._map_widget is None:
            return
        for m in self._markers:
            m.delete()
        self._markers.clear()
