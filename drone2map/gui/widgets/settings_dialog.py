"""Dialog: Projekt- und App-Einstellungen."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog
from ...core.project import ProjectSettings
from ...config.settings import AppSettings


class SettingsDialog(tk.Toplevel):
    """Modaler Dialog für Projekt- und ODM-Einstellungen."""

    def __init__(self, master, project_settings: ProjectSettings,
                 app_settings: AppSettings, **kwargs):
        super().__init__(master, **kwargs)
        self.title("Einstellungen")
        self.resizable(False, False)
        self.grab_set()
        self._ps = project_settings
        self._as = app_settings
        self._result: ProjectSettings | None = None
        self._vars: dict[str, tk.Variable] = {}
        self._build()
        self.transient(master)
        self.wait_window()

    @property
    def result(self) -> ProjectSettings | None:
        return self._result

    def _build(self) -> None:
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        # ---- Tab: Ausgabe ----
        tab_out = ttk.Frame(nb)
        nb.add(tab_out, text="Ausgabe")
        self._add_str_field(tab_out, 0, "Ausgabeverzeichnis", "output_dir",
                            str(self._as.output_dir), browse=True)

        # ---- Tab: ODM-Parameter ----
        tab_odm = ttk.Frame(nb)
        nb.add(tab_odm, text="ODM-Parameter")
        ps = self._ps
        self._add_bool_field(tab_odm, 0, "DSM erzeugen", "dsm", ps.dsm)
        self._add_bool_field(tab_odm, 1, "DTM erzeugen", "dtm", ps.dtm)
        self._add_float_field(tab_odm, 2, "Orthofoto-Auflösung (cm/px)", "orthophoto_resolution",
                              ps.orthophoto_resolution)
        self._add_combo_field(tab_odm, 3, "Feature-Qualität", "feature_quality",
                              ps.feature_quality, ["lowest","low","medium","high","ultra"])
        self._add_combo_field(tab_odm, 4, "PC-Qualität", "pc_quality",
                              ps.pc_quality, ["lowest","low","medium","high","ultra"])
        self._add_int_field(tab_odm, 5, "Mesh-Octree-Tiefe", "mesh_octree_depth",
                            ps.mesh_octree_depth)

        # ---- Tab: NodeODM ----
        tab_node = ttk.Frame(nb)
        nb.add(tab_node, text="NodeODM")
        self._add_str_field(tab_node, 0, "Host", "node_host", ps.node_host)
        self._add_int_field(tab_node, 1, "Port", "node_port", ps.node_port)
        self._node_status_var = tk.StringVar(value="")
        ttk.Button(tab_node, text="Verbindung testen",
                   command=self._test_nodeodm_connection).grid(
            row=2, column=0, columnspan=2, pady=(12, 4), padx=8, sticky="w")
        ttk.Label(tab_node, textvariable=self._node_status_var,
                  anchor="w").grid(row=3, column=0, columnspan=3, sticky="w", padx=8)

        # ---- Buttons ----
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text="Speichern", style="success.TButton",
                   command=self._save).pack(side="right", padx=(4, 0))
        ttk.Button(btn_frame, text="Abbrechen", command=self.destroy).pack(side="right")

    def _add_bool_field(self, parent, row, label, key, value) -> None:
        var = tk.BooleanVar(value=value)
        self._vars[key] = var
        ttk.Label(parent, text=label, width=28, anchor="e").grid(row=row, column=0, sticky="e", padx=8, pady=4)
        ttk.Checkbutton(parent, variable=var).grid(row=row, column=1, sticky="w", padx=8, pady=4)

    def _add_str_field(self, parent, row, label, key, value, browse=False) -> None:
        var = tk.StringVar(value=value)
        self._vars[key] = var
        ttk.Label(parent, text=label, width=28, anchor="e").grid(row=row, column=0, sticky="e", padx=8, pady=4)
        ent = ttk.Entry(parent, textvariable=var, width=32)
        ent.grid(row=row, column=1, sticky="w", padx=(8, 0), pady=4)
        if browse:
            ttk.Button(parent, text="…", width=3,
                       command=lambda: var.set(filedialog.askdirectory() or var.get())
                       ).grid(row=row, column=2, padx=4)

    def _add_float_field(self, parent, row, label, key, value) -> None:
        var = tk.DoubleVar(value=value)
        self._vars[key] = var
        ttk.Label(parent, text=label, width=28, anchor="e").grid(row=row, column=0, sticky="e", padx=8, pady=4)
        ttk.Entry(parent, textvariable=var, width=12).grid(row=row, column=1, sticky="w", padx=8, pady=4)

    def _add_int_field(self, parent, row, label, key, value) -> None:
        var = tk.IntVar(value=value)
        self._vars[key] = var
        ttk.Label(parent, text=label, width=28, anchor="e").grid(row=row, column=0, sticky="e", padx=8, pady=4)
        ttk.Entry(parent, textvariable=var, width=12).grid(row=row, column=1, sticky="w", padx=8, pady=4)

    def _add_combo_field(self, parent, row, label, key, value, choices) -> None:
        var = tk.StringVar(value=value)
        self._vars[key] = var
        ttk.Label(parent, text=label, width=28, anchor="e").grid(row=row, column=0, sticky="e", padx=8, pady=4)
        ttk.Combobox(parent, textvariable=var, values=choices, state="readonly", width=12
                     ).grid(row=row, column=1, sticky="w", padx=8, pady=4)

    def _test_nodeodm_connection(self) -> None:
        """Testet die NodeODM-Verbindung mit den aktuell eingetragenen Werten."""
        try:
            host = str(self._vars["node_host"].get())
            port = int(self._vars["node_port"].get())
        except (KeyError, ValueError):
            self._node_status_var.set("⚠ Ungültige Host/Port-Angabe")
            return
        self._node_status_var.set("⏳ Verbinde…")
        self.update_idletasks()
        try:
            from ...processing.odm_runner import OdmRunner
            available = OdmRunner(host=host, port=port).is_nodeodm_available()
        except Exception as exc:
            self._node_status_var.set(f"✗ Fehler: {exc}")
            return
        if available:
            self._node_status_var.set(f"✓ NodeODM erreichbar auf {host}:{port}")
        else:
            self._node_status_var.set(f"✗ NodeODM nicht erreichbar auf {host}:{port}")

    def _save(self) -> None:
        try:
            self._as.output_dir = self._vars["output_dir"].get()
            self._result = ProjectSettings(
                dsm=bool(self._vars["dsm"].get()),
                dtm=bool(self._vars["dtm"].get()),
                orthophoto_resolution=float(self._vars["orthophoto_resolution"].get()),
                feature_quality=str(self._vars["feature_quality"].get()),
                pc_quality=str(self._vars["pc_quality"].get()),
                mesh_octree_depth=int(self._vars["mesh_octree_depth"].get()),
                node_host=str(self._vars["node_host"].get()),
                node_port=int(self._vars["node_port"].get()),
            )
        except (ValueError, KeyError) as exc:
            from tkinter import messagebox
            messagebox.showerror("Ungültige Eingabe",
                                 f"Bitte alle Felder korrekt ausfüllen:\n{exc}",
                                 parent=self)
            return
        self.destroy()
