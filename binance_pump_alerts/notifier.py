"""Alerts: Windows toast notification (winotify) + our own sound (winsound) + alerts.log.

The sound is played by the app itself instead of the toast, because Windows often mutes
toast sounds (Focus assist, per-app notification settings). Toasts are shown in a
background thread, so a slow PowerShell call never delays price checks.

On non-Windows systems (e.g. when testing) everything falls back to console output.
"""

from __future__ import annotations

import threading
import time
from decimal import Decimal

from .settings import APP_NAME, alerts_log_path

try:
    from winotify import Notification, audio
except ImportError:  # not on Windows / package missing
    Notification = None
    audio = None

try:
    import winsound
except ImportError:  # not on Windows
    winsound = None

_sound_lock = threading.Lock()


def _format_price(price: float) -> str:
    return format(Decimal(str(price)).normalize(), "f")


def _append_log(line: str) -> None:
    """Record an alert / problem in alerts.log (never raises)."""
    try:
        path = alerts_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {line}\n")
    except OSError:
        pass


def play_sound() -> None:
    """Play a short two-tone beep without blocking the caller."""
    if winsound is None:
        return

    def _play() -> None:
        if not _sound_lock.acquire(blocking=False):  # a sound is already playing
            return
        try:
            try:
                winsound.Beep(988, 160)
                winsound.Beep(1319, 240)
            except RuntimeError:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        finally:
            _sound_lock.release()

    threading.Thread(target=_play, name="alert-sound", daemon=True).start()


def _show_toast(title: str, message: str, link: str | None) -> None:
    try:
        if Notification is None:
            print(f"[notification] {title}: {message}")
            return
        toast = Notification(app_id=APP_NAME, title=title, msg=message, duration="long")
        toast.set_audio(audio.Silent, loop=False)  # sound is played by play_sound()
        if link:
            toast.add_actions(label="Open on Binance", launch=link)
        toast.show()
    except Exception as exc:
        _append_log(f"TOAST FAILED for '{title}': {exc}")


def _notify(title: str, message: str, link: str | None, sound: bool) -> None:
    if sound:
        play_sound()
    threading.Thread(target=_show_toast, args=(title, message, link), daemon=True).start()


def show_alert(symbol: str, change_percent: float, price: float, window_minutes: int, sound: bool = True) -> None:
    """Pump alert with the coin ticker in the title."""
    message = f"Price rose {change_percent:.2f}% in {window_minutes} min. Current price: {_format_price(price)}"
    _append_log(f"ALERT {symbol} +{change_percent:.2f}% in {window_minutes} min, price {_format_price(price)}")
    _notify(
        title=f"{symbol}  +{change_percent:.2f}%",
        message=message,
        link=f"https://www.binance.com/en/futures/{symbol}",
        sound=sound,
    )


def show_test(sound: bool = True) -> None:
    _notify("Test notification", "Notifications are working.", None, sound)
