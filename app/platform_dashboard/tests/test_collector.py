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
