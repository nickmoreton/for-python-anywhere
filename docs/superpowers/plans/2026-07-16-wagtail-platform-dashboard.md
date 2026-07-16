# Wagtail Platform Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an administrator-only Platform dashboard to the Wagtail sidebar that displays a safe page-load snapshot of application and infrastructure information.

**Architecture:** A dedicated `app.platform_dashboard` Django app registers one Wagtail admin URL and one superuser-only menu item. A request-independent collector returns immutable, presentation-ready snapshot records; the view enforces superuser access and passes those records to a Wagtail-styled template. Each external metric boundary degrades independently to `Unavailable`.

**Tech Stack:** Python 3.13, Django 6.0, Wagtail 7.4, psutil 7.x, Django templates, Django/Wagtail test utilities, UV.

## Global Constraints

- The page is read-only and served at `/admin/platform/`.
- The sidebar label is `Platform`, with Wagtail's built-in `cogs` icon.
- Anonymous users are redirected through Wagtail's admin login flow.
- Authenticated Wagtail admin non-superusers receive HTTP 403. Authenticated users without Wagtail admin access follow Wagtail's standard admin-login redirect. Only superusers can view the page or its sidebar item.
- Values are collected once per request with no polling, background jobs, charts, or network access.
- Collection is allowlist-based and never exposes secrets, credentials, environment-variable contents, database connection details, request data, or full settings.
- Disk values describe the filesystem containing Django's `BASE_DIR`, not a PythonAnywhere account quota.
- Uptime means the current Django process uptime, not machine or site uptime.
- Missing or restricted individual readings display `Unavailable` without breaking the page.
- Git runs without a shell, with a one-second timeout, and returns only the short current commit SHA.
- No database model or migration is added.

---

## File Structure

- Create `app/platform_dashboard/__init__.py`: mark the new Python package.
- Create `app/platform_dashboard/apps.py`: define the Django app configuration.
- Create `app/platform_dashboard/collector.py`: own snapshot record types, safe metric boundaries, system readers, and display formatting.
- Create `app/platform_dashboard/views.py`: enforce superuser access and render one snapshot.
- Create `app/platform_dashboard/wagtail_hooks.py`: register the admin route and superuser-only sidebar item.
- Create `app/platform_dashboard/templates/platform_dashboard/index.html`: render the two snapshot sections with Wagtail admin components and styles.
- Create `app/platform_dashboard/tests/__init__.py`: mark the test package.
- Create `app/platform_dashboard/tests/test_collector.py`: test formatting, collection, and failure isolation without a database.
- Create `app/platform_dashboard/tests/test_admin.py`: test the registered route, access control, menu policy, rendering, and secret absence.
- Modify `app/settings/base.py`: install the new app.
- Modify `pyproject.toml` and `uv.lock`: add and lock psutil 7.x.
- Modify `AGENTS.md`: document the new app in the repository map.

---

### Task 1: Add the app skeleton and deterministic value formatting

**Files:**
- Create: `app/platform_dashboard/__init__.py`
- Create: `app/platform_dashboard/apps.py`
- Create: `app/platform_dashboard/collector.py`
- Create: `app/platform_dashboard/tests/__init__.py`
- Create: `app/platform_dashboard/tests/test_collector.py`
- Modify: `app/settings/base.py:38-42`
- Modify: `pyproject.toml:7-13`
- Modify: `uv.lock`

**Interfaces:**
- Consumes: Django settings and timezone utilities; psutil 7.x is installed now for later metric readers.
- Produces: `PlatformField(label: str, value: str, status: str = "")`, `PlatformSection(title: str, fields: tuple[PlatformField, ...])`, `PlatformSnapshot(collected_at: datetime, sections: tuple[PlatformSection, ...])`, `format_bytes(value: int | float) -> str`, and `format_duration(seconds: int | float) -> str`.

- [ ] **Step 1: Create the package markers and write failing formatter tests**

Create empty files at `app/platform_dashboard/__init__.py` and `app/platform_dashboard/tests/__init__.py`. Create `app/platform_dashboard/tests/test_collector.py` with:

```python
from datetime import datetime

from django.test import SimpleTestCase
from django.utils import timezone

from app.platform_dashboard.collector import (
    PlatformField,
    PlatformSection,
    PlatformSnapshot,
    format_bytes,
    format_duration,
)


class PlatformRecordTests(SimpleTestCase):
    def test_snapshot_records_are_immutable_and_keep_section_order(self):
        collected_at = timezone.now()
        field = PlatformField(label="Python", value="3.13.5")
        section = PlatformSection(title="Application", fields=(field,))
        snapshot = PlatformSnapshot(
            collected_at=collected_at,
            sections=(section,),
        )

        self.assertEqual(snapshot.collected_at, collected_at)
        self.assertEqual(snapshot.sections[0].fields[0].value, "3.13.5")
        self.assertIsInstance(snapshot.collected_at, datetime)
        with self.assertRaises(AttributeError):
            snapshot.collected_at = timezone.now()

    def test_format_bytes_uses_binary_units(self):
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(1536), "1.5 KiB")
        self.assertEqual(format_bytes(5 * 1024**3), "5.0 GiB")

    def test_format_duration_includes_each_nonzero_unit(self):
        self.assertEqual(format_duration(0), "0s")
        self.assertEqual(format_duration(61), "1m 1s")
        self.assertEqual(format_duration(90_061), "1d 1h 1m 1s")
```

- [ ] **Step 2: Run the focused test and confirm the missing collector failure**

Run:

```bash
uv run python manage.py test app.platform_dashboard.tests.test_collector
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.platform_dashboard.collector'`.

- [ ] **Step 3: Add psutil to the project lock and install the Django app**

Run:

```bash
uv add "psutil>=7,<8"
```

Expected: `pyproject.toml` contains `"psutil>=7,<8"` in `dependencies`, `uv.lock` locks a compatible psutil release, and the environment sync completes successfully.

Create `app/platform_dashboard/apps.py`:

```python
from django.apps import AppConfig


class PlatformDashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.platform_dashboard"
    verbose_name = "Platform dashboard"
```

Add the app before `app.home` in `app/settings/base.py`:

```python
INSTALLED_APPS = [
    "app.platform_dashboard",
    "app.home",
    "app.search",
```

- [ ] **Step 4: Implement the immutable records and formatters**

Create `app/platform_dashboard/collector.py`:

```python
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
```

- [ ] **Step 5: Run the formatter tests and Django checks**

Run:

```bash
uv run python manage.py test app.platform_dashboard.tests.test_collector
uv run python manage.py check
```

Expected: 3 tests pass and Django reports `System check identified no issues`.

- [ ] **Step 6: Commit the app foundation**

```bash
git add app/platform_dashboard app/settings/base.py pyproject.toml uv.lock
git commit -m "feat: add platform dashboard foundation"
```

---

### Task 2: Collect application and infrastructure snapshots safely

**Files:**
- Modify: `app/platform_dashboard/collector.py`
- Modify: `app/platform_dashboard/tests/test_collector.py`

**Interfaces:**
- Consumes: Task 1's immutable record classes and formatting functions.
- Produces: `collect_platform_snapshot() -> PlatformSnapshot`; all later HTTP code depends only on this function and the returned record properties.

- [ ] **Step 1: Write failing tests for a complete snapshot**

Append these imports to `app/platform_dashboard/tests/test_collector.py`:

```python
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from django.test import override_settings
```

Add `collect_platform_snapshot` to the existing collector import and append:

```python
@override_settings(DEBUG=True, BASE_DIR="/srv/wagtail")
class PlatformCollectorTests(SimpleTestCase):
    @patch("app.platform_dashboard.collector.time.time", return_value=1_000_061)
    @patch("app.platform_dashboard.collector.psutil.Process")
    @patch("app.platform_dashboard.collector.psutil.disk_usage")
    @patch("app.platform_dashboard.collector.psutil.virtual_memory")
    @patch("app.platform_dashboard.collector.psutil.cpu_percent", return_value=12.5)
    @patch(
        "app.platform_dashboard.collector.psutil.cpu_count",
        side_effect=(4, 8),
    )
    @patch("app.platform_dashboard.collector.platform.machine", return_value="x86_64")
    @patch("app.platform_dashboard.collector.platform.release", return_value="6.8")
    @patch("app.platform_dashboard.collector.platform.system", return_value="Linux")
    @patch("app.platform_dashboard.collector._git_commit", return_value="abc1234")
    @patch("app.platform_dashboard.collector.socket.gethostname", return_value="web-1")
    @patch("app.platform_dashboard.collector.wagtail.__version__", "7.4.2")
    @patch("app.platform_dashboard.collector.django.get_version", return_value="6.0.7")
    @patch("app.platform_dashboard.collector.platform.python_version", return_value="3.13.5")
    def test_collects_allowlisted_application_and_infrastructure_fields(
        self,
        _python_version,
        _django_version,
        _hostname,
        _git,
        _system,
        _release,
        _machine,
        cpu_count,
        _cpu_percent,
        virtual_memory,
        disk_usage,
        process_class,
        _time,
    ):
        virtual_memory.return_value = SimpleNamespace(
            total=8 * 1024**3,
            used=3 * 1024**3,
            available=5 * 1024**3,
            percent=37.5,
        )
        disk_usage.return_value = SimpleNamespace(
            total=100 * 1024**3,
            used=40 * 1024**3,
            free=60 * 1024**3,
            percent=40.0,
        )
        process_class.return_value.create_time.return_value = 1_000_000

        snapshot = collect_platform_snapshot()
        sections = {section.title: section for section in snapshot.sections}
        application = {
            field.label: field.value for field in sections["Application"].fields
        }
        infrastructure = {
            field.label: field.value
            for field in sections["Infrastructure"].fields
        }

        self.assertTrue(timezone.is_aware(snapshot.collected_at))
        self.assertEqual(application["Environment"], "Development")
        self.assertEqual(application["Python"], "3.13.5")
        self.assertEqual(application["Django"], "6.0.7")
        self.assertEqual(application["Wagtail"], "7.4.2")
        self.assertEqual(application["Database engine"], "MySQL")
        self.assertEqual(application["Debug"], "Enabled")
        self.assertEqual(application["Hostname"], "web-1")
        self.assertEqual(application["Git commit"], "abc1234")
        self.assertEqual(infrastructure["Operating system"], "Linux 6.8")
        self.assertEqual(infrastructure["Architecture"], "x86_64")
        self.assertEqual(infrastructure["Physical CPU cores"], "4")
        self.assertEqual(infrastructure["Logical CPU cores"], "8")
        self.assertEqual(infrastructure["CPU utilization"], "12.5%")
        self.assertEqual(
            infrastructure["Memory"],
            "8.0 GiB total · 3.0 GiB used · 5.0 GiB available · 37.5% used",
        )
        self.assertEqual(
            infrastructure["Project filesystem"],
            "100.0 GiB total · 40.0 GiB used · 60.0 GiB free · 40.0% used",
        )
        self.assertEqual(infrastructure["Django process uptime"], "1m 1s")
        cpu_count.assert_has_calls((call(logical=False), call(logical=True)))
        disk_usage.assert_called_once_with("/srv/wagtail")
```

- [ ] **Step 2: Write failing tests for unavailable and unexpected metrics**

Add `MetricSpec` and `_collect_field` to the collector imports, then append inside `PlatformCollectorTests`:

```python
    def test_expected_metric_failure_returns_unavailable_without_logging_traceback(self):
        spec = MetricSpec(label="Git commit", name="git_commit", reader=Mock())
        spec.reader.side_effect = OSError("git is unavailable")

        field = _collect_field(spec)

        self.assertEqual(
            field,
            PlatformField(
                label="Git commit",
                value="Unavailable",
                status="unavailable",
            ),
        )

    def test_unexpected_metric_failure_is_logged_without_rendering_exception(self):
        spec = MetricSpec(label="Python", name="python_version", reader=Mock())
        spec.reader.side_effect = AssertionError("private failure detail")

        with self.assertLogs(
            "app.platform_dashboard.collector",
            level="ERROR",
        ) as logs:
            field = _collect_field(spec)

        self.assertEqual(field.value, "Unavailable")
        self.assertNotIn("private failure detail", field.value)
        self.assertIn("python_version", logs.output[0])

    @patch("app.platform_dashboard.collector.subprocess.run")
    def test_git_lookup_is_bounded_and_does_not_use_a_shell(self, run):
        run.return_value.stdout = "abc1234\n"

        self.assertEqual(_git_commit(), "abc1234")

        run.assert_called_once_with(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd="/srv/wagtail",
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        )
```

Add `_git_commit` to the collector imports. The absence of a `shell` argument means Python's safe default `shell=False` is used.

- [ ] **Step 3: Run the collector tests and confirm the missing interface failures**

Run:

```bash
uv run python manage.py test app.platform_dashboard.tests.test_collector
```

Expected: FAIL because `MetricSpec`, `_collect_field`, `_git_commit`, and `collect_platform_snapshot` are not defined.

- [ ] **Step 4: Implement safe metric boundaries and the snapshot collector**

Replace `app/platform_dashboard/collector.py` with:

```python
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
```

- [ ] **Step 5: Run the collector tests and fix only test-discovered defects**

Run:

```bash
uv run python manage.py test app.platform_dashboard.tests.test_collector
```

Expected: all 8 collector tests pass, including snapshot-level failure isolation. Confirm the snapshot tests complete promptly despite the bounded 0.1-second CPU sample.

- [ ] **Step 6: Commit the safe collector**

```bash
git add app/platform_dashboard/collector.py app/platform_dashboard/tests/test_collector.py
git commit -m "feat: collect platform dashboard metrics"
```

---

### Task 3: Register and render the administrator-only Wagtail page

**Files:**
- Create: `app/platform_dashboard/views.py`
- Create: `app/platform_dashboard/wagtail_hooks.py`
- Create: `app/platform_dashboard/templates/platform_dashboard/index.html`
- Create: `app/platform_dashboard/tests/test_admin.py`

**Interfaces:**
- Consumes: `collect_platform_snapshot() -> PlatformSnapshot` from Task 2 and Wagtail's `register_admin_urls`, `register_admin_menu_item`, `AdminOnlyMenuItem`, and admin URL wrapper.
- Produces: URL name `platform_dashboard`, path `/admin/platform/`, `platform_dashboard.views.index(request)`, and a `Platform` sidebar link returned by `register_platform_menu_item()`.

- [ ] **Step 1: Write failing access-control and route tests**

Create `app/platform_dashboard/tests/test_admin.py`:

```python
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from app.platform_dashboard.collector import (
    PlatformField,
    PlatformSection,
    PlatformSnapshot,
)


class PlatformDashboardAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.superuser = user_model.objects.create_superuser(
            username="platform-admin",
            email="admin@example.com",
            password="password",
        )
        cls.editor = user_model.objects.create_user(
            username="platform-editor",
            email="editor@example.com",
            password="password",
        )
        cls.editor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="wagtailadmin",
                codename="access_admin",
            )
        )

    def test_anonymous_user_is_redirected_to_wagtail_login(self):
        response = self.client.get(reverse("platform_dashboard"))

        self.assertRedirects(
            response,
            f'{reverse("wagtailadmin_login")}?next={reverse("platform_dashboard")}',
            fetch_redirect_response=False,
        )

    def test_non_superuser_receives_forbidden(self):
        self.client.force_login(self.editor)

        response = self.client.get(reverse("platform_dashboard"))

        self.assertEqual(response.status_code, 403)

    @patch("app.platform_dashboard.views.collect_platform_snapshot")
    def test_superuser_sees_snapshot_sections(self, collect_snapshot):
        collect_snapshot.return_value = PlatformSnapshot(
            collected_at=timezone.now(),
            sections=(
                PlatformSection(
                    title="Application",
                    fields=(PlatformField("Python", "3.13.5"),),
                ),
                PlatformSection(
                    title="Infrastructure",
                    fields=(
                        PlatformField(
                            "Project filesystem",
                            "100.0 GiB total",
                        ),
                        PlatformField(
                            "Git commit",
                            "Unavailable",
                            status="unavailable",
                        ),
                    ),
                ),
            ),
        )
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("platform_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "platform_dashboard/index.html")
        self.assertContains(response, "Platform")
        self.assertContains(response, "Application")
        self.assertContains(response, "Infrastructure")
        self.assertContains(response, "Python")
        self.assertContains(response, "3.13.5")
        self.assertContains(response, "Unavailable")
        self.assertContains(response, "project filesystem, not a hosting account quota")
        collect_snapshot.assert_called_once_with()
```

- [ ] **Step 2: Write failing menu visibility and secret-absence tests**

Append to `app/platform_dashboard/tests/test_admin.py`:

```python
    def test_platform_menu_item_is_only_shown_to_superusers(self):
        from app.platform_dashboard.wagtail_hooks import (
            register_platform_menu_item,
        )

        menu_item = register_platform_menu_item()
        request_factory = RequestFactory()
        editor_request = request_factory.get("/admin/")
        editor_request.user = self.editor
        admin_request = request_factory.get("/admin/")
        admin_request.user = self.superuser

        self.assertEqual(menu_item.label, "Platform")
        self.assertEqual(menu_item.url, reverse("platform_dashboard"))
        self.assertFalse(menu_item.is_shown(editor_request))
        self.assertTrue(menu_item.is_shown(admin_request))

    @patch("app.platform_dashboard.views.collect_platform_snapshot")
    def test_response_does_not_render_secret_or_database_credentials(
        self,
        collect_snapshot,
    ):
        collect_snapshot.return_value = PlatformSnapshot(
            collected_at=timezone.now(),
            sections=(
                PlatformSection(
                    title="Application",
                    fields=(PlatformField("Database engine", "MySQL"),),
                ),
            ),
        )
        self.client.force_login(self.superuser)

        with self.settings(
            SECRET_KEY="dashboard-secret-sentinel",
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.mysql",
                    "NAME": "private-database-sentinel",
                    "USER": "private-user-sentinel",
                    "PASSWORD": "private-password-sentinel",
                    "HOST": "private-host-sentinel",
                    "PORT": 3306,
                }
            },
        ):
            response = self.client.get(reverse("platform_dashboard"))

        self.assertContains(response, "MySQL")
        self.assertNotContains(response, "dashboard-secret-sentinel")
        self.assertNotContains(response, "private-database-sentinel")
        self.assertNotContains(response, "private-user-sentinel")
        self.assertNotContains(response, "private-password-sentinel")
        self.assertNotContains(response, "private-host-sentinel")
```

- [ ] **Step 3: Run the admin tests and confirm URL registration fails**

Run:

```bash
uv run python manage.py test app.platform_dashboard.tests.test_admin
```

Expected: FAIL because the `platform_dashboard` URL, view, hook module, and template do not exist.

- [ ] **Step 4: Implement the superuser-only view**

Create `app/platform_dashboard/views.py`:

```python
from django.http import HttpResponseForbidden
from django.shortcuts import render

from app.platform_dashboard.collector import collect_platform_snapshot


def index(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden()

    return render(
        request,
        "platform_dashboard/index.html",
        {
            "page_title": "Platform",
            "header_title": "Platform",
            "header_icon": "cogs",
            "snapshot": collect_platform_snapshot(),
        },
    )
```

Do not raise `PermissionDenied` here: Wagtail's outer admin wrapper converts that exception into a redirect. Returning `HttpResponseForbidden` preserves the design's explicit HTTP 403 result for an authenticated Wagtail admin non-superuser. Wagtail's registered-admin-URL wrapper redirects anonymous users and authenticated users without admin access before this view runs.

- [ ] **Step 5: Register the admin URL and menu item**

Create `app/platform_dashboard/wagtail_hooks.py`:

```python
from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import AdminOnlyMenuItem

from app.platform_dashboard import views


@hooks.register("register_admin_urls")
def register_platform_admin_urls():
    return [
        path("platform/", views.index, name="platform_dashboard"),
    ]


@hooks.register("register_admin_menu_item")
def register_platform_menu_item():
    return AdminOnlyMenuItem(
        "Platform",
        reverse("platform_dashboard"),
        name="platform-dashboard",
        icon_name="cogs",
        order=8990,
    )
```

- [ ] **Step 6: Render the Wagtail-styled snapshot**

Create `app/platform_dashboard/templates/platform_dashboard/index.html`:

```django
{% extends "wagtailadmin/generic/base.html" %}

{% block titletag %}Platform{% endblock %}

{% block main_content %}
    <p class="help-block w-mb-8">
        Snapshot collected {{ snapshot.collected_at|date:"DATETIME_FORMAT" }}.
        Values update when this page is reloaded.
    </p>

    {% for section in snapshot.sections %}
        <section class="w-mb-10" aria-labelledby="platform-section-{{ forloop.counter }}">
            <h2 id="platform-section-{{ forloop.counter }}" class="w-h2">
                {{ section.title }}
            </h2>
            <table class="listing">
                <thead>
                    <tr>
                        <th scope="col">Detail</th>
                        <th scope="col">Value</th>
                    </tr>
                </thead>
                <tbody>
                    {% for field in section.fields %}
                        <tr>
                            <th scope="row">{{ field.label }}</th>
                            <td{% if field.status %} data-status="{{ field.status }}"{% endif %}>
                                {{ field.value }}
                            </td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </section>
    {% endfor %}

    <p class="help-block">
        Disk values describe the project filesystem, not a hosting account quota.
        Uptime is for the current Django process, not the machine or site.
    </p>
{% endblock %}
```

- [ ] **Step 7: Run the admin and complete app tests**

Run:

```bash
uv run python manage.py test app.platform_dashboard.tests.test_admin
uv run python manage.py test app.platform_dashboard
```

Expected: 6 admin tests pass and all 14 platform dashboard tests pass, including an authenticated non-admin redirect test and snapshot-level failure isolation. If Django's redirect query encoding differs, inspect `response.url` and update only the expected URL to Django's actual encoded `next` value; do not weaken the redirect assertion.

- [ ] **Step 8: Commit the Wagtail integration**

```bash
git add app/platform_dashboard/views.py app/platform_dashboard/wagtail_hooks.py app/platform_dashboard/templates app/platform_dashboard/tests/test_admin.py
git commit -m "feat: add Wagtail platform dashboard"
```

---

### Task 4: Update repository guidance and run full verification

**Files:**
- Modify: `AGENTS.md:7-12`

**Interfaces:**
- Consumes: the completed dashboard app and existing repository verification commands.
- Produces: accurate repository guidance and evidence that the feature integrates without migrations or regressions.

- [ ] **Step 1: Update the documented project structure**

In `AGENTS.md`, replace the existing `app/home/` and `app/search/` bullets with these three bullets:

```markdown
- `app/home/` defines the `HomePage`, its migrations, templates, app-specific static files, and public-page tests.
- `app/platform_dashboard/` defines the superuser-only Wagtail Platform dashboard, its runtime metric collector, admin hooks and template, and its tests.
- `app/search/` contains the search view and template.
```

No command documentation changes are needed: psutil is installed through the existing `uv sync --locked` and Docker lockfile workflows.

- [ ] **Step 2: Run the full Django verification suite**

Run:

```bash
uv run python manage.py test
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Expected: the full test suite passes, Django reports no issues, and migration checking reports `No changes detected`.

If the configured host MySQL service is unavailable, start the repository's Compose database and repeat the exact commands in the web service after rebuilding the locked image:

```bash
docker compose build web
docker compose run --rm web python manage.py test
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
```

Expected: the same passing results against the Compose MySQL service.

- [ ] **Step 3: Run relevant asset and deployment invariant checks**

The dashboard adds no custom frontend assets or deployment workflow edits, but its new locked Python dependency must remain compatible with those paths. Run:

```bash
bash scripts/test-asset-pipeline.sh
bash scripts/test-container-assets.sh
bash scripts/test-workflow-assets.sh
bash scripts/test-deployment-invariants.sh
bash scripts/test-deploy-failures.sh
```

Expected: every script exits with status 0.

- [ ] **Step 4: Inspect the final diff for secrets, generated migrations, and unrelated changes**

Run:

```bash
git status --short
git diff --check
git diff --stat HEAD~3
git diff HEAD~3 -- app/platform_dashboard app/settings/base.py pyproject.toml AGENTS.md
```

Expected: only the planned dashboard, dependency lock, settings, tests, and `AGENTS.md` changes are present; whitespace checking is clean; no migration file, credential value, generated static asset, or unrelated edit appears.

- [ ] **Step 5: Commit the repository guidance**

```bash
git add AGENTS.md
git commit -m "docs: document platform dashboard app"
```

- [ ] **Step 6: Re-run final status and focused smoke checks after the commit**

Run:

```bash
git status --short
uv run python manage.py test app.platform_dashboard
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Expected: the working tree is clean, all platform dashboard tests pass, Django reports no issues, and no model changes are detected.
