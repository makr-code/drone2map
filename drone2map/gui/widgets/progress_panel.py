"""Widget: Fortschrittsanzeige für die Verarbeitung."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk


class ProgressPanel(ttk.LabelFrame):
    """Zeigt Fortschrittsbalken und Log-Ausgabe der Verarbeitung."""

    def __init__(self, master, **kwargs):
        super().__init__(master, text="Verarbeitung", **kwargs)
        self._build()

    def _build(self) -> None:
        self._pct_var = tk.DoubleVar(value=0.0)
        self._status_var = tk.StringVar(value="Bereit")

        ttk.Label(self, textvariable=self._status_var, anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        self._bar = ttk.Progressbar(self, variable=self._pct_var, maximum=100, mode="determinate")
        self._bar.pack(fill="x", padx=8, pady=(0, 4))

        # Log-Textfeld
        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._log = tk.Text(log_frame, height=8, state="disabled",
                            font=("Consolas", 9), wrap="word",
                            bg="#1a1a1a", fg="#cccccc", insertbackground="white")
        vsb = ttk.Scrollbar(log_frame, orient="vertical", command=self._log.yview)
        self._log.configure(yscrollcommand=vsb.set)
        self._log.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=(0, 6))
        self._start_btn = ttk.Button(btn_frame, text="▶ Starten", style="success.TButton")
        self._start_btn.pack(side="left", padx=(0, 6))
        self._stop_btn = ttk.Button(btn_frame, text="⏹ Abbrechen", style="danger.TButton", state="disabled")
        self._stop_btn.pack(side="left")

    def set_progress(self, pct: float, message: str) -> None:
        """Aktualisiert Fortschrittsbalken und Statustext (thread-safe via after)."""
        if pct >= 0:
            self._pct_var.set(min(pct, 100.0))
        self._status_var.set(message)
        self._append_log(message)

    def _append_log(self, text: str) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def set_running(self, running: bool) -> None:
        """Wechselt zwischen Laufend- und Bereit-Zustand."""
        if running:
            self._start_btn.configure(state="disabled")
            self._stop_btn.configure(state="normal")
            self._bar.configure(mode="indeterminate")
            self._bar.start(15)
        else:
            self._start_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")
            self._bar.stop()
            self._bar.configure(mode="determinate")

    def set_start_command(self, cmd) -> None:
        self._start_btn.configure(command=cmd)

    def set_stop_command(self, cmd) -> None:
        self._stop_btn.configure(command=cmd)

    def clear_log(self) -> None:
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._pct_var.set(0.0)
        self._status_var.set("Bereit")
