"""Sayı, boyut ve tarihleri Türkçe biçimde gösterme yardımcıları."""

from __future__ import annotations

from datetime import datetime

_MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def format_size(num_bytes: float) -> str:
    """Bayt değerini okunabilir biçime çevirir (örn. 3,4 MB)."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            text = f"{num_bytes:.1f}" if unit != "B" else f"{int(num_bytes)}"
            return f"{text.replace('.', ',')} {unit}"
        num_bytes /= 1024
    return f"{num_bytes} TB"


def format_count(n: int) -> str:
    """Binlik ayırıcı olarak nokta kullanır (41.286)."""
    return f"{n:,}".replace(",", ".")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def format_date(value: str | None, with_time: bool = True) -> str:
    """ISO tarihini "14 Ağu 2025 18:42" biçimine çevirir."""
    dt = parse_iso(value)
    if dt is None:
        return "—"
    text = f"{dt.day} {_MONTHS[dt.month - 1]} {dt.year}"
    return f"{text} {dt:%H:%M}" if with_time else text


def format_time(value: str | None) -> str:
    dt = parse_iso(value)
    return f"{dt:%H:%M:%S}" if dt else "—"
