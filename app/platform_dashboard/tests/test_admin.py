from unittest.mock import patch

from django.conf import settings
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
        cls.member = user_model.objects.create_user(
            username="platform-member",
            email="member@example.com",
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

    def test_authenticated_user_without_admin_access_is_redirected_to_login(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("platform_dashboard"))

        self.assertRedirects(
            response,
            f'{reverse("wagtailadmin_login")}?next={reverse("platform_dashboard")}',
            fetch_redirect_response=False,
        )

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
        private_database_values = {
            "NAME": "private-database-sentinel",
            "USER": "private-user-sentinel",
            "PASSWORD": "private-password-sentinel",
            "HOST": "private-host-sentinel",
        }
        with self.settings(SECRET_KEY="dashboard-secret-sentinel"):
            with patch.dict(settings.DATABASES["default"], private_database_values):
                self.client.force_login(self.superuser)
                response = self.client.get(reverse("platform_dashboard"))

        self.assertContains(response, "MySQL")
        self.assertNotContains(response, "dashboard-secret-sentinel")
        self.assertNotContains(response, "private-database-sentinel")
        self.assertNotContains(response, "private-user-sentinel")
        self.assertNotContains(response, "private-password-sentinel")
        self.assertNotContains(response, "private-host-sentinel")
