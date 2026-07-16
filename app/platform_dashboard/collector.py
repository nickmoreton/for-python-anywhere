import logging
import platform
import socket
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import django
import psutil
import wagtail
from django.conf import settings
from django.db import connections
from django.utils import timezone


logger = logging.getLogger(__name__)
UNAVAILABLE = "Unavailable"


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


@dataclass(frozen=True)
class MetricSpec:
    label: str
    name: str
    reader: Callable[[], Any]
    formatter: Callable[[Any], str] = str


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


def _collect_field(spec: MetricSpec) -> PlatformField:
    try:
        raw_value = spec.reader()
        if raw_value is None or raw_value == "":
            raise RuntimeError("metric returned no value")
        return PlatformField(label=spec.label, value=spec.formatter(raw_value))
    except (OSError, RuntimeError, subprocess.SubprocessError, psutil.Error):
        return PlatformField(
            label=spec.label,
            value=UNAVAILABLE,
            status="unavailable",
        )
    except Exception:
        logger.error("Unexpected failure collecting platform metric %s", spec.name)
        return PlatformField(
            label=spec.label,
            value=UNAVAILABLE,
            status="unavailable",
        )


def _database_vendor() -> str:
    names = {
        "mysql": "MySQL",
        "postgresql": "PostgreSQL",
        "sqlite": "SQLite",
        "oracle": "Oracle",
    }
    vendor = connections["default"].vendor
    return names.get(vendor, vendor.replace("_", " ").title())


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=settings.BASE_DIR,
        check=True,
        capture_output=True,
        text=True,
        timeout=1,
    )
    return result.stdout.strip()


def _operating_system() -> str:
    return f"{platform.system()} {platform.release()}".strip()


def _memory_summary() -> str:
    memory = psutil.virtual_memory()
    return (
        f"{format_bytes(memory.total)} total · "
        f"{format_bytes(memory.used)} used · "
        f"{format_bytes(memory.available)} available · "
        f"{memory.percent:.1f}% used"
    )


def _disk_summary() -> str:
    disk = psutil.disk_usage(settings.BASE_DIR)
    return (
        f"{format_bytes(disk.total)} total · "
        f"{format_bytes(disk.used)} used · "
        f"{format_bytes(disk.free)} free · "
        f"{disk.percent:.1f}% used"
    )


def _process_uptime() -> float:
    return time.time() - psutil.Process().create_time()


def _application_metrics() -> tuple[MetricSpec, ...]:
    return (
        MetricSpec(
            label="Environment",
            name="environment",
            reader=lambda: "Development" if settings.DEBUG else "Production",
        ),
        MetricSpec(
            label="Python",
            name="python_version",
            reader=platform.python_version,
        ),
        MetricSpec(
            label="Django",
            name="django_version",
            reader=django.get_version,
        ),
        MetricSpec(
            label="Wagtail",
            name="wagtail_version",
            reader=lambda: wagtail.__version__,
        ),
        MetricSpec(
            label="Database engine",
            name="database_vendor",
            reader=_database_vendor,
        ),
        MetricSpec(
            label="Debug",
            name="debug_status",
            reader=lambda: "Enabled" if settings.DEBUG else "Disabled",
        ),
        MetricSpec(
            label="Hostname",
            name="hostname",
            reader=socket.gethostname,
        ),
        MetricSpec(
            label="Git commit",
            name="git_commit",
            reader=_git_commit,
        ),
    )


def _infrastructure_metrics() -> tuple[MetricSpec, ...]:
    return (
        MetricSpec(
            label="Operating system",
            name="operating_system",
            reader=_operating_system,
        ),
        MetricSpec(
            label="Architecture",
            name="architecture",
            reader=platform.machine,
        ),
        MetricSpec(
            label="Physical CPU cores",
            name="physical_cpu_cores",
            reader=lambda: psutil.cpu_count(logical=False),
        ),
        MetricSpec(
            label="Logical CPU cores",
            name="logical_cpu_cores",
            reader=lambda: psutil.cpu_count(logical=True),
        ),
        MetricSpec(
            label="CPU utilization",
            name="cpu_utilization",
            reader=lambda: psutil.cpu_percent(interval=0.1),
            formatter=lambda value: f"{value:.1f}%",
        ),
        MetricSpec(
            label="Memory",
            name="memory",
            reader=_memory_summary,
        ),
        MetricSpec(
            label="Project filesystem",
            name="project_filesystem",
            reader=_disk_summary,
        ),
        MetricSpec(
            label="Django process uptime",
            name="process_uptime",
            reader=_process_uptime,
            formatter=format_duration,
        ),
    )


def collect_platform_snapshot() -> PlatformSnapshot:
    return PlatformSnapshot(
        collected_at=timezone.now(),
        sections=(
            PlatformSection(
                title="Application",
                fields=tuple(_collect_field(spec) for spec in _application_metrics()),
            ),
            PlatformSection(
                title="Infrastructure",
                fields=tuple(
                    _collect_field(spec) for spec in _infrastructure_metrics()
                ),
            ),
        ),
    )
