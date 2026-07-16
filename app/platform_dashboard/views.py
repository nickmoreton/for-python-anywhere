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
