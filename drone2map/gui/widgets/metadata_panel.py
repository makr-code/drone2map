"""Widget: Metadaten-Panel für ein einzelnes Bild."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional
from ...core.exif_parser import ImageMetadata


class MetadataPanel(ttk.LabelFrame):
    """Zeigt EXIF-Metadaten eines ausgewählten Bildes."""

    def __init__(self, master, **kwargs):
        super().__init__(master, text="Bilddetails", **kwargs)
        self._vars: dict[str, tk.StringVar] = {}
        self._build()

    def _build(self) -> None:
        fields = [
            ("Datei", "filename"),
            ("Kamera", "camera"),
            ("Datum", "datetime"),
            ("GPS", "gps"),
            ("Breite", "latitude"),
            ("Länge", "longitude"),
            ("Höhe (m)", "altitude"),
            ("Brennweite (mm)", "focal"),
            ("ISO", "iso"),
            ("Belichtung", "exposure"),
            ("Auflösung", "resolution"),
        ]
        for i, (label, key) in enumerate(fields):
            ttk.Label(self, text=f"{label}:", anchor="e", width=16).grid(row=i, column=0, sticky="e", padx=(8, 4), pady=2)
            var = tk.StringVar(value="—")
            ttk.Label(self, textvariable=var, anchor="w").grid(row=i, column=1, sticky="w", pady=2)
            self._vars[key] = var
        self.columnconfigure(1, weight=1)

    def show(self, meta: Optional[ImageMetadata]) -> None:
        """Füllt das Panel mit den Daten des übergebenen Bildes."""
        if meta is None:
            for v in self._vars.values():
                v.set("—")
            return
        self._vars["filename"].set(meta.filename)
        self._vars["camera"].set(f"{meta.camera_make} {meta.camera_model}".strip() or "—")
        self._vars["datetime"].set(meta.datetime_original or "—")
        gps_text = "✓ vorhanden" if meta.gps_valid else "✗ fehlt"
        self._vars["gps"].set(gps_text)
        self._vars["latitude"].set(f"{meta.latitude:.6f}" if meta.latitude is not None else "—")
        self._vars["longitude"].set(f"{meta.longitude:.6f}" if meta.longitude is not None else "—")
        self._vars["altitude"].set(f"{meta.altitude:.1f}" if meta.altitude is not None else "—")
        self._vars["focal"].set(f"{meta.focal_length:.1f}" if meta.focal_length is not None else "—")
        self._vars["iso"].set(str(meta.iso) if meta.iso is not None else "—")
        self._vars["exposure"].set(meta.exposure_time or "—")
        if meta.image_width and meta.image_height:
            self._vars["resolution"].set(f"{meta.image_width} × {meta.image_height}")
        else:
            self._vars["resolution"].set("—")
