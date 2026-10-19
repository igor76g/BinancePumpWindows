"""Tkinter window: settings form, Start/Stop buttons, status line and log."""

from __future__ import annotations

import os
import queue
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from . import __version__, notifier
from .binance_api import BinanceApi
from .monitor import Monitor
from .settings import APP_NAME, Settings, alerts_log_path, load_settings, save_settings

MAX_LOG_LINES = 500

# (settings key, label, python type, minimum allowed value)
FIELDS = [
    ("Volume filter", None, None, None),
    ("min_volume_million_usdt", "Minimum 24h volume (million USDT)", float, 0.0),
    ("volume_refresh_sec", "Volume list refresh interval (seconds)", int, 1),
    ("Price pump filter", None, None, None),
    ("price_change_percent", "Minimum price growth (%)", float, 0.01),
    ("window_minutes", "Time window (minutes)", int, 1),
    ("General", None, None, None),
    ("check_interval_sec", "Price check interval (seconds)", int, 1),
    ("cooldown_minutes", "Alert cooldown per coin (minutes)", int, 0),
]


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {__version__}")
        self.minsize(560, 640)

        self.api = BinanceApi()
        self.monitor: Monitor | None = None
        self.messages: queue.Queue = queue.Queue()
        self.vars: dict[str, tk.StringVar] = {}
        self.labels: dict[str, str] = {}
        self.types: dict[str, tuple] = {}
        self.autostart_var = tk.BooleanVar(value=False)
        self.sound_var = tk.BooleanVar(value=True)

        self._build_widgets()
        settings = load_settings()
        self._show_settings(settings)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(200, self._drain_messages)
        if settings.autostart_monitoring:
            self.after(500, self.start_monitoring)

    # ------------------------------------------------------------------ UI

    def _build_widgets(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="Binance Futures Pump Alerts", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        self.status_var = tk.StringVar(value="Stopped")
        ttk.Label(root, textvariable=self.status_var, wraplength=520).pack(anchor="w", pady=(4, 10))

        form = ttk.Frame(root)
        form.pack(fill="x")
        form.columnconfigure(0, weight=1)

        row = 0
        for key, label, py_type, minimum in FIELDS:
            if label is None:  # section header
                ttk.Label(form, text=key, font=("Segoe UI", 10, "bold")).grid(
                    row=row, column=0, columnspan=2, sticky="w", pady=(10, 2)
                )
            else:
                var = tk.StringVar()
                self.vars[key] = var
                self.labels[key] = label
                self.types[key] = (py_type, minimum)
                ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=2)
                ttk.Entry(form, textvariable=var, width=14).grid(row=row, column=1, sticky="e", pady=2)
            row += 1

        ttk.Checkbutton(
            root, text="Start monitoring automatically when the app opens", variable=self.autostart_var
        ).pack(anchor="w", pady=(12, 0))
        ttk.Checkbutton(root, text="Play a sound on every alert", variable=self.sound_var).pack(anchor="w")

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=12)
        self.save_button = ttk.Button(buttons, text="Save settings", command=self.save_clicked)
        self.save_button.pack(side="left")
        self.start_button = ttk.Button(buttons, text="Start monitoring", command=self.start_monitoring)
        self.start_button.pack(side="left", padx=6)
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.stop_monitoring, state="disabled")
        self.stop_button.pack(side="left")
        ttk.Button(buttons, text="Test notification", command=self.test_notification).pack(side="right")
        ttk.Button(buttons, text="Alerts log", command=self.open_alerts_log).pack(side="right", padx=6)

        ttk.Label(root, text="Log", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.log_widget = scrolledtext.ScrolledText(root, height=12, state="disabled", wrap="word")
        self.log_widget.pack(fill="both", expand=True)

    def _show_settings(self, s: Settings) -> None:
        for key, var in self.vars.items():
            value = getattr(s, key)
            var.set(f"{value:g}" if isinstance(value, float) else str(value))
        self.autostart_var.set(s.autostart_monitoring)
        self.sound_var.set(s.sound_enabled)

    def _read_form(self) -> Settings | None:
        """Validate the form. Shows an error dialog and returns None if something is invalid."""
        values: dict = {}
        for key, var in self.vars.items():
            py_type, minimum = self.types[key]
            raw = var.get().strip().replace(",", ".")
            try:
                value = py_type(raw)
            except ValueError:
                messagebox.showerror(APP_NAME, f"'{self.labels[key]}' must be a valid number.")
                return None
            if value < minimum:
                messagebox.showerror(APP_NAME, f"'{self.labels[key]}' must be at least {minimum:g}.")
                return None
            values[key] = value
        return Settings(
            autostart_monitoring=self.autostart_var.get(),
            sound_enabled=self.sound_var.get(),
            **values,
        )

    # ------------------------------------------------------------- actions

    def save_clicked(self) -> Settings | None:
        settings = self._read_form()
        if settings is None:
            return None
        try:
            save_settings(settings)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Could not save settings: {exc}")
            return None
        self.add_log("Settings saved")
        return settings

    def start_monitoring(self) -> None:
        if self.monitor is not None and self.monitor.is_alive():
            return
        if self.save_clicked() is None:
            return
        self.monitor = Monitor(
            api=self.api,
            load_settings=load_settings,
            notify=lambda symbol, change, price, window: notifier.show_alert(
                symbol, change, price, window, sound=load_settings().sound_enabled
            ),
            log=lambda text: self.messages.put(("log", text)),
            set_status=lambda text: self.messages.put(("status", text)),
        )
        self.monitor.start()
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_var.set("Starting...")

    def stop_monitoring(self) -> None:
        if self.monitor is not None:
            self.monitor.stop()
        self.stop_button.config(state="disabled")

    def test_notification(self) -> None:
        try:
            notifier.show_test(sound=self.sound_var.get())
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not show notification: {exc}")

    def open_alerts_log(self) -> None:
        """Open alerts.log (every alert with time, coin, growth and price) in Notepad."""
        path = alerts_log_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
            os.startfile(str(path))  # Windows only
        except (OSError, AttributeError) as exc:
            messagebox.showerror(APP_NAME, f"Could not open {path}: {exc}")

    # ---------------------------------------------------------------- misc

    def add_log(self, text: str) -> None:
        self.log_widget.config(state="normal")
        self.log_widget.insert("end", f"{time.strftime('%H:%M:%S')}  {text}\n")
        lines = int(self.log_widget.index("end-1c").split(".")[0])
        if lines > MAX_LOG_LINES:
            self.log_widget.delete("1.0", f"{lines - MAX_LOG_LINES + 1}.0")
        self.log_widget.see("end")
        self.log_widget.config(state="disabled")

    def _drain_messages(self) -> None:
        """Move messages from the monitor thread into the UI (runs on the UI thread)."""
        try:
            while True:
                kind, text = self.messages.get_nowait()
                if kind == "log":
                    self.add_log(text)
                else:
                    self.status_var.set(text)
        except queue.Empty:
            pass

        if self.monitor is not None and not self.monitor.is_alive():
            self.monitor = None
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")
        self.after(200, self._drain_messages)

    def _on_close(self) -> None:
        if self.monitor is not None:
            self.monitor.stop()
        self.destroy()


def main() -> None:
    App().mainloop()
