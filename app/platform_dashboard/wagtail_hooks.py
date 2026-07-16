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
