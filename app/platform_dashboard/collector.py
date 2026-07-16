from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PlatformField:
    label: str
    value: str
    status: str = ""


@dataclass(frozen=True)
class PlatformSection:
    title: str
    fields: tuple[PlatformField, ...]


@dataclass(frozen=True)
class PlatformSnapshot:
    collected_at: datetime
    sections: tuple[PlatformSection, ...]


def format_bytes(value: int | float) -> str:
    size = float(value)
    units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")

    for unit in units:
        if abs(size) < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{size:.0f} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024

    raise AssertionError("byte formatter exhausted its unit list")


def format_duration(seconds: int | float) -> str:
    remaining = max(0, int(seconds))
    days, remaining = divmod(remaining, 86_400)
    hours, remaining = divmod(remaining, 3_600)
    minutes, seconds = divmod(remaining, 60)
    parts = []

    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts)
