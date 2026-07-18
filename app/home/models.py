from django.db import models

from wagtail.models import Page


class HomePage(Page):
    def get_context(self, request, *args, **kwargs):
        from app.blog.models import BlogIndexPage

        context = super().get_context(request, *args, **kwargs)
        context["blog_page"] = (
            BlogIndexPage.objects.child_of(self).live().public().first()
        )
        return context
