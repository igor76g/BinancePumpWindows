"""Background monitoring loop.

Every `check_interval_sec` seconds:
  1. (periodically) refresh the list of coins whose 24h quote volume >= minimum volume,
  2. fetch current prices and track them over a rolling window,
  3. fire a notification when growth within the window >= threshold.

Settings are re-read on every iteration, so changes saved in the window apply
without restarting the monitor.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

from .price_tracker import PriceTracker
from .settings import Settings


class Monitor(threading.Thread):
    def __init__(
        self,
        api,
        load_settings: Callable[[], Settings],
        notify: Callable[[str, float, float, int], None],
        log: Callable[[str], None],
        set_status: Callable[[str], None],
    ) -> None:
        super().__init__(name="monitor", daemon=True)
        self.api = api
        self.load_settings = load_settings
        self.notify = notify
        self.log = log
        self.set_status = set_status

        self.tracker = PriceTracker()
        self.qualifying: set[str] = set()
        self._last_volume_refresh: float | None = None
        self._last_alert: dict[str, float] = {}
        self._stopping = threading.Event()

    def stop(self) -> None:
        self._stopping.set()

    def run(self) -> None:
        self.log("Monitoring started")
        while not self._stopping.is_set():
            settings = self.load_settings()
            try:
                self.tick(settings, time.time())
            except Exception as exc:  # network errors, bad responses, etc.
                self.log(f"Error: {exc} (retrying)")
                self.set_status(f"Error: {exc} (retrying)")
            self._stopping.wait(max(1, settings.check_interval_sec))
        self.set_status("Stopped")
        self.log("Monitoring stopped")

    def tick(self, settings: Settings, now: float) -> None:
        """One monitoring iteration. `now` is a Unix timestamp in seconds."""
        # 1) Periodically refresh which coins pass the 24h volume filter
        refresh_sec = max(1, settings.volume_refresh_sec)
        if self._last_volume_refresh is None or now - self._last_volume_refresh >= refresh_sec:
            symbols = self.api.usdt_perpetual_symbols()
            volumes = self.api.quote_volumes()
            qualifying = {s for s in symbols if volumes.get(s, 0.0) >= settings.min_volume_usdt}
            if qualifying != self.qualifying:
                self.log(
                    f"Coins with 24h volume >= {settings.min_volume_million_usdt:g}M USDT: {len(qualifying)}"
                )
            self.qualifying = qualifying
            self.tracker.retain_only(qualifying)
            self._last_volume_refresh = now

        # 2) Poll prices and detect pumps
        prices = self.api.prices()
        window_sec = max(1, settings.window_minutes) * 60
        cooldown_sec = max(0, settings.cooldown_minutes) * 60

        for symbol in sorted(self.qualifying):
            price = prices.get(symbol)
            if price is None:
                continue
            self.tracker.add(symbol, price, now, window_sec)
            change = self.tracker.change_percent(symbol)
            if change is None or change < settings.price_change_percent:
                continue

            last = self._last_alert.get(symbol)
            if last is not None and now - last < cooldown_sec:
                continue
            self._last_alert[symbol] = now

            self.log(f"ALERT {symbol}: +{change:.2f}% in {settings.window_minutes} min (price {price:g})")
            try:
                self.notify(symbol, change, price, settings.window_minutes)
            except Exception as exc:  # a notification problem must not stop monitoring
                self.log(f"Could not show notification: {exc}")

        self.set_status(
            f"Watching {len(self.qualifying)} coins. Last check: {time.strftime('%H:%M:%S')}"
        )
