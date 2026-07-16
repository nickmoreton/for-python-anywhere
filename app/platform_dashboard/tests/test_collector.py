from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from app.platform_dashboard.collector import (
    MetricSpec,
    PlatformField,
    PlatformSection,
    PlatformSnapshot,
    _collect_field,
    _git_commit,
    collect_platform_snapshot,
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
