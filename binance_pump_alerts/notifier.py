"""Windows toast notifications (via winotify). Falls back to a simple console print
when winotify is not available (e.g. when testing on another OS)."""

from __future__ import annotations

from decimal import Decimal

from .settings import APP_NAME

try:
    from winotify import Notification, audio
except ImportError:  # not on Windows / package missing
    Notification = None
    audio = None


def _format_price(price: float) -> str:
    return format(Decimal(str(price)).normalize(), "f")


def _show(title: str, message: str, link: str | None = None) -> None:
    if Notification is None:
        print(f"[notification] {title}: {message}")
        return
    toast = Notification(app_id=APP_NAME, title=title, msg=message, duration="long")
    toast.set_audio(audio.Default, loop=False)
    if link:
        toast.add_actions(label="Open on Binance", launch=link)
    toast.show()


def show_alert(symbol: str, change_percent: float, price: float, window_minutes: int) -> None:
    """Pump alert with the coin ticker in the title."""
    _show(
        title=f"{symbol}  +{change_percent:.2f}%",
        message=f"Price rose {change_percent:.2f}% in {window_minutes} min. Current price: {_format_price(price)}",
        link=f"https://www.binance.com/en/futures/{symbol}",
    )


def show_test() -> None:
    _show("Test notification", "Notifications are working.")
