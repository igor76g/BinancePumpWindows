"""User-editable settings, stored as JSON in %APPDATA%\\BinancePumpAlerts\\settings.json."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

APP_NAME = "Binance Pump Alerts"


@dataclass
class Settings:
    """Defaults match the requested conditions:
    24h volume > 30M USDT and price growth > 4% within 5 minutes."""

    # --- Volume filter ---
    min_volume_million_usdt: float = 30.0   # minimum 24h quote volume, in millions of USDT
    volume_refresh_sec: int = 60            # how often to refresh the list of qualifying coins

    # --- Price pump filter ---
    price_change_percent: float = 4.0       # minimum price growth within the window, in %
    window_minutes: int = 5                 # time window used to measure price growth

    # --- General ---
    check_interval_sec: int = 15            # how often to poll current prices
    cooldown_minutes: int = 15              # don't re-alert the same coin within this time
    autostart_monitoring: bool = False      # start monitoring as soon as the app opens
    sound_enabled: bool = True              # play a sound on every alert

    @property
    def min_volume_usdt(self) -> float:
        return self.min_volume_million_usdt * 1_000_000.0


def settings_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "BinancePumpAlerts" / "settings.json"


def alerts_log_path() -> Path:
    """Text file where every alert (and notification problem) is recorded."""
    return settings_path().parent / "alerts.log"


def load_settings() -> Settings:
    """Load settings from disk. Missing or broken values fall back to the defaults."""
    defaults = Settings()
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaults
    if not isinstance(data, dict):
        return defaults

    values = {}
    for field in fields(Settings):
        if field.name not in data:
            continue
        expected_type = type(getattr(defaults, field.name))
        try:
            values[field.name] = expected_type(data[field.name])
        except (TypeError, ValueError):
            pass
    return Settings(**values)


def save_settings(settings: Settings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
