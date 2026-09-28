"""Jinja filters mirroring the Django template filters we relied on."""
from datetime import datetime


def filesizeformat(value) -> str:
    """Human-readable size, roughly matching Django's |filesizeformat."""
    try:
        size = float(value or 0)
    except (TypeError, ValueError):
        return "0 bytes"
    if size < 1024:
        return f"{int(size)} bytes"
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
    return f"{size:.1f} TB"


def fmt_dt(value) -> str:
    """Format a datetime like Django's 'M j, Y, g:i a' -> 'Jan 5, 2026, 3:04 p.m.'."""
    if not isinstance(value, datetime):
        return "" if value is None else str(value)
    hour = value.hour % 12 or 12
    ampm = "a.m." if value.hour < 12 else "p.m."
    return f"{value.strftime('%b')} {value.day}, {value.year}, {hour}:{value.minute:02d} {ampm}"
