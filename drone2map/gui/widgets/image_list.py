"""Widget: Liste der geladenen Bilder mit GPS-Status."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Callable, Optional
from ...core.exif_parser import ImageMetadata


class ImageListWidget(ttk.Frame):
    """Zeigt eine scrollbare Liste von Drohnenbildern mit GPS-Status."""

    def __init__(self, master, on_select: Optional[Callable[[str], None]] = None,
                 on_remove: Optional[Callable[[list[str]], None]] = None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_select = on_select
        self._on_remove = on_remove
        self._items: dict[str, ImageMetadata] = {}
        self._build()

    def _build(self) -> None:
        cols = ("filename", "gps", "lat", "lon", "alt")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        self._tree.heading("filename", text="Datei")
        self._tree.heading("gps", text="GPS")
        self._tree.heading("lat", text="Breite")
        self._tree.heading("lon", text="Länge")
        self._tree.heading("alt", text="Höhe (m)")
        self._tree.column("filename", width=220, anchor="w")
        self._tree.column("gps", width=45, anchor="center")
        self._tree.column("lat", width=100, anchor="e")
        self._tree.column("lon", width=100, anchor="e")
        self._tree.column("alt", width=80, anchor="e")

        vsb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._tree.tag_configure("ok", foreground="#00bc8c")
        self._tree.tag_configure("nogps", foreground="#e74c3c")
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self._tree.bind("<Delete>", lambda _: self._remove_selected())

        # Rechtsklick-Kontextmenü
        self._ctx_menu = tk.Menu(self._tree, tearoff=False)
        self._ctx_menu.add_command(label="Ausgewählte entfernen", command=self._remove_selected)
        self._ctx_menu.add_command(label="Alles entfernen", command=self._remove_all)
        self._tree.bind("<Button-3>", self._show_context_menu)

    def set_images(self, images: list[ImageMetadata]) -> None:
        """Setzt die angezeigte Bildliste."""
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._items.clear()
        for meta in images:
            gps = "✓" if meta.gps_valid else "✗"
            lat = f"{meta.latitude:.6f}" if meta.latitude is not None else "—"
            lon = f"{meta.longitude:.6f}" if meta.longitude is not None else "—"
            alt = f"{meta.altitude:.1f}" if meta.altitude is not None else "—"
            tag = "ok" if meta.gps_valid else "nogps"
            iid = self._tree.insert("", "end", values=(meta.filename, gps, lat, lon, alt), tags=(tag,))
            self._items[iid] = meta

    def get_selected_paths(self) -> list[str]:
        return [self._items[iid].file_path for iid in self._tree.selection() if iid in self._items]

    def _on_tree_select(self, _event) -> None:
        sel = self._tree.selection()
        if sel and self._on_select and sel[0] in self._items:
            self._on_select(self._items[sel[0]].file_path)

    def _show_context_menu(self, event: tk.Event) -> None:
        """Zeigt das Kontextmenü an der Mausposition."""
        row = self._tree.identify_row(event.y)
        if row and row not in self._tree.selection():
            self._tree.selection_set(row)
        n_selected = len(self._tree.selection())
        label = f"Ausgewählte entfernen ({n_selected})" if n_selected else "Ausgewählte entfernen"
        self._ctx_menu.entryconfigure(0, label=label,
                                      state="normal" if n_selected else "disabled")
        self._ctx_menu.tk_popup(event.x_root, event.y_root)

    def _remove_selected(self) -> None:
        """Entfernt die selektierten Einträge und ruft den on_remove-Callback."""
        paths = self.get_selected_paths()
        if not paths:
            return
        for iid in list(self._tree.selection()):
            self._tree.delete(iid)
            self._items.pop(iid, None)
        if self._on_remove:
            self._on_remove(paths)

    def _remove_all(self) -> None:
        """Entfernt alle Einträge und ruft den on_remove-Callback."""
        paths = [m.file_path for m in self._items.values()]
        self.clear()
        if self._on_remove and paths:
            self._on_remove(paths)

    def clear(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._items.clear()
