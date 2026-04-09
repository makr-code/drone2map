"""Hauptfenster der drone2map Anwendung."""
from __future__ import annotations

import logging
import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Optional

from ..config.settings import AppSettings
from ..core.exif_parser import ExifParser, ImageMetadata, SUPPORTED_EXTENSIONS
from ..core.project import Project, ProjectSettings
from ..processing.pipeline import (
    Pipeline,
    ProgressEvent,
    MetadataEvent,
    DoneEvent,
    ErrorEvent,
)
from .widgets.image_list import ImageListWidget
from .widgets.map_view import MapViewWidget
from .widgets.metadata_panel import MetadataPanel
from .widgets.progress_panel import ProgressPanel
from .widgets.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)

try:
    import ttkbootstrap as ttk_bs  # type: ignore
    _HAS_BOOTSTRAP = True
except ImportError:
    _HAS_BOOTSTRAP = False


class App:
    """Haupt-GUI-Klasse."""

    def __init__(self, settings: AppSettings):
        self._settings = settings
        self._project: Optional[Project] = None
        self._pipeline: Optional[Pipeline] = None
        self._metadata: list[ImageMetadata] = []
        self._exif_parser = ExifParser()

        if _HAS_BOOTSTRAP:
            self._root = ttk_bs.Window(themename=settings.theme)
        else:
            self._root = tk.Tk()

        self._root.title("drone2map")
        self._root.geometry("1280x800")
        self._root.minsize(900, 600)
        self._build_menu()
        self._build_ui()
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def run(self) -> None:
        self._root.mainloop()

    # ------------------------------------------------------------------ #
    # Menü                                                                 #
    # ------------------------------------------------------------------ #

    def _build_menu(self) -> None:
        menubar = tk.Menu(self._root)
        self._root.configure(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Datei", menu=file_menu)
        file_menu.add_command(label="Neues Projekt", accelerator="Ctrl+N", command=self._new_project)
        file_menu.add_command(label="Projekt öffnen…", accelerator="Ctrl+O", command=self._open_project)
        file_menu.add_command(label="Projekt speichern", accelerator="Ctrl+S", command=self._save_project)
        file_menu.add_separator()
        file_menu.add_command(label="Bilder hinzufügen…", command=self._add_images)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self._on_close)

        self._root.bind("<Control-n>", lambda _: self._new_project())
        self._root.bind("<Control-o>", lambda _: self._open_project())
        self._root.bind("<Control-s>", lambda _: self._save_project())

        settings_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Einstellungen", menu=settings_menu)
        settings_menu.add_command(label="Einstellungen…", command=self._open_settings)

        help_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Hilfe", menu=help_menu)
        help_menu.add_command(label="Über drone2map", command=self._about)

    # ------------------------------------------------------------------ #
    # Layout                                                               #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        # Toolbar
        toolbar = ttk.Frame(self._root)
        toolbar.pack(side="top", fill="x", padx=6, pady=4)
        ttk.Button(toolbar, text="+ Bilder", command=self._add_images).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Ordner", command=self._add_folder).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Alles löschen", command=self._clear_images).pack(side="left", padx=2)

        # Haupt-PanedWindow
        paned = ttk.PanedWindow(self._root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # Linke Seite: Bildliste + Metadaten
        left = ttk.Frame(paned)
        paned.add(left, weight=1)
        self._image_list = ImageListWidget(left, on_select=self._on_image_select)
        self._image_list.pack(fill="both", expand=True)
        self._meta_panel = MetadataPanel(left)
        self._meta_panel.pack(fill="x", pady=(4, 0))

        # Rechte Seite: Karte + Fortschritt
        right = ttk.Frame(paned)
        paned.add(right, weight=2)
        self._map_view = MapViewWidget(right)
        self._map_view.pack(fill="both", expand=True)
        self._progress = ProgressPanel(right)
        self._progress.pack(fill="x", pady=(4, 0))
        self._progress.set_start_command(self._start_processing)
        self._progress.set_stop_command(self._stop_processing)

        # Statusleiste
        self._status_var = tk.StringVar(value="Bereit – kein Projekt geladen")
        status_bar = ttk.Label(self._root, textvariable=self._status_var,
                               relief="sunken", anchor="w")
        status_bar.pack(side="bottom", fill="x")

    # ------------------------------------------------------------------ #
    # Aktionen                                                             #
    # ------------------------------------------------------------------ #

    def _new_project(self) -> None:
        name = simpledialog.askstring("Neues Projekt", "Projektname:", parent=self._root)
        if not name:
            return
        output = filedialog.askdirectory(title="Ausgabeverzeichnis wählen")
        if not output:
            return
        self._project = Project(name=name, output_dir=output)
        self._metadata.clear()
        self._image_list.clear()
        self._map_view.clear()
        self._meta_panel.show(None)
        self._status(f"Projekt: {name}")

    def _open_project(self) -> None:
        path = filedialog.askopenfilename(
            title="Projekt öffnen", filetypes=[("drone2map Projekt", "*.d2m.json"), ("JSON", "*.json")])
        if not path:
            return
        try:
            self._project = Project.load(path)
            self._settings.add_recent(path)
            self._settings.last_project = path
            self._reload_images()
            self._status(f"Projekt geladen: {self._project.name}")
        except Exception as exc:
            messagebox.showerror("Fehler", f"Projekt konnte nicht geladen werden:\n{exc}")

    def _save_project(self) -> None:
        if self._project is None:
            messagebox.showinfo("Hinweis", "Kein Projekt geöffnet")
            return
        if not self._project.file_path:
            path = filedialog.asksaveasfilename(
                title="Projekt speichern",
                defaultextension=".d2m.json",
                filetypes=[("drone2map Projekt", "*.d2m.json")])
            if not path:
                return
        else:
            path = self._project.file_path
        try:
            self._project.save(path)
            self._status(f"Gespeichert: {path}")
        except Exception as exc:
            messagebox.showerror("Fehler", f"Speichern fehlgeschlagen:\n{exc}")

    def _add_images(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Bilder hinzufügen",
            filetypes=[("Bilder", "*.jpg *.jpeg *.tif *.tiff *.png"), ("Alle", "*.*")])
        if not paths:
            return
        self._ensure_project()
        added = self._project.add_images(list(paths))  # type: ignore[union-attr]
        self._reload_images()
        self._status(f"{added} Bilder hinzugefügt ({self._project.image_count} gesamt)")  # type: ignore[union-attr]

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Ordner mit Bildern wählen")
        if not folder:
            return
        self._ensure_project()
        paths = [str(p) for p in Path(folder).iterdir()
                 if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
        added = self._project.add_images(paths)  # type: ignore[union-attr]
        self._reload_images()
        self._status(f"{added} Bilder aus Ordner hinzugefügt")

    def _clear_images(self) -> None:
        if self._project is None:
            return
        if messagebox.askyesno("Bestätigen", "Alle Bilder aus dem Projekt entfernen?"):
            self._project.image_paths.clear()
            self._metadata.clear()
            self._image_list.clear()
            self._map_view.clear()
            self._meta_panel.show(None)
            self._status("Bildliste geleert")

    def _reload_images(self) -> None:
        if self._project is None:
            return
        self._metadata = [self._exif_parser.parse_file(p) for p in self._project.image_paths]
        self._image_list.set_images(self._metadata)
        self._map_view.set_images(self._metadata)

    def _on_image_select(self, path: str) -> None:
        meta = next((m for m in self._metadata if m.file_path == path), None)
        self._meta_panel.show(meta)
        if meta and meta.has_valid_coordinates:
            self._map_view.center_on(meta.latitude, meta.longitude)

    def _open_settings(self) -> None:
        if self._project is None:
            self._ensure_project()
        dlg = SettingsDialog(self._root,
                             project_settings=self._project.settings,  # type: ignore[union-attr]
                             app_settings=self._settings)
        if dlg.result:
            self._project.settings = dlg.result  # type: ignore[union-attr]
            self._settings.save()

    def _start_processing(self) -> None:
        if self._project is None or not self._project.is_ready:
            messagebox.showwarning("Nicht bereit",
                                   "Mindestens 3 Bilder und ein Ausgabeverzeichnis erforderlich.")
            return
        self._progress.clear_log()
        self._progress.set_running(True)
        self._pipeline = Pipeline(self._project)
        self._pipeline.run_async()
        self._root.after(50, self._poll_queue)

    def _poll_queue(self) -> None:
        """Pollt die Pipeline-Event-Queue und aktualisiert die GUI (läuft im GUI-Thread)."""
        if self._pipeline is None:
            return
        try:
            while True:
                event = self._pipeline.event_queue.get_nowait()
                if isinstance(event, ProgressEvent):
                    self._progress.set_progress(event.percent, event.message)
                elif isinstance(event, MetadataEvent):
                    self._image_list.set_images(event.metadata)
                elif isinstance(event, DoneEvent):
                    self._on_processing_done(event.result_paths)
                    return
                elif isinstance(event, ErrorEvent):
                    self._on_processing_error(event.message)
                    return
        except queue.Empty:
            pass
        self._root.after(50, self._poll_queue)

    def _stop_processing(self) -> None:
        if self._pipeline:
            self._pipeline.stop()
        self._progress.set_running(False)
        self._status("Verarbeitung abgebrochen")

    def _on_processing_done(self, results: dict) -> None:
        self._progress.set_running(False)
        self._status(f"Fertig! {len(results)} Ergebnisse erstellt.")
        messagebox.showinfo("Fertig", f"Verarbeitung abgeschlossen.\nErgebnisse in:\n{self._project.output_dir}")  # type: ignore[union-attr]

    def _on_processing_error(self, msg: str) -> None:
        self._progress.set_running(False)
        self._status(f"Fehler: {msg}")
        messagebox.showerror("Verarbeitungsfehler", msg)

    def _about(self) -> None:
        from .. import __version__
        messagebox.showinfo("Über drone2map",
                            f"drone2map v{__version__}\n\nDrohnenbilder zu Orthofoto, DSM und DGM.\n"
                            "Powered by OpenDroneMap (ODM).")

    def _on_close(self) -> None:
        self._settings.save()
        self._root.destroy()

    # ------------------------------------------------------------------ #
    # Hilfsmethoden                                                        #
    # ------------------------------------------------------------------ #

    def _ensure_project(self) -> None:
        if self._project is None:
            self._project = Project(
                name="Unbenannt",
                output_dir=self._settings.output_dir,
                settings=ProjectSettings(
                    node_host=self._settings.odm.node_host,
                    node_port=self._settings.odm.node_port,
                ),
            )

    def _status(self, msg: str) -> None:
        self._status_var.set(msg)
        logger.info(msg)

