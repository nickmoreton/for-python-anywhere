import os

from django.conf import settings
from django.test import SimpleTestCase


class EnvironmentSettingsTests(SimpleTestCase):
    def test_mysql_settings_match_environment(self):
        database = settings.DATABASES["default"]

        self.assertEqual(database["ENGINE"], "django.db.backends.mysql")
        self.assertEqual(database["NAME"], os.environ["MYSQL_DATABASE"])
        self.assertEqual(database["USER"], os.environ["MYSQL_USER"])
        self.assertEqual(database["PASSWORD"], os.environ["MYSQL_PASSWORD"])
        self.assertEqual(database["HOST"], os.environ["MYSQL_HOST"])
        self.assertEqual(database["PORT"], int(os.environ["MYSQL_PORT"]))
        self.assertEqual(database["OPTIONS"], {"charset": "utf8mb4"})

    def test_web_security_settings_match_environment(self):
        self.assertEqual(settings.SECRET_KEY, os.environ["DJANGO_SECRET_KEY"])
        # Django's test runner appends its default client host at runtime.
        self.assertEqual(settings.ALLOWED_HOSTS[:2], ["localhost", "127.0.0.1"])
        self.assertEqual(settings.ALLOWED_HOSTS[2:], ["testserver"])
        self.assertEqual(
            settings.CSRF_TRUSTED_ORIGINS,
            ["http://localhost:8000"],
        )
        self.assertEqual(
            settings.WAGTAILADMIN_BASE_URL,
            os.environ["WAGTAILADMIN_BASE_URL"],
        )
        self.assertEqual(settings.STATIC_ROOT, settings.BASE_DIR / "staticfiles")
