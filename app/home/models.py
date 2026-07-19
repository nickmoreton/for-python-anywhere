from django.db import models

from wagtail.admin.panels import FieldPanel
from wagtail.models import Page


class HomePage(Page):
    featured_post = models.ForeignKey(
        "blog.BlogPostPage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    content_panels = Page.content_panels + [FieldPanel("featured_post")]

    def get_context(self, request, *args, **kwargs):
        from app.blog.models import BlogIndexPage

        context = super().get_context(request, *args, **kwargs)
        context["blog_page"] = (
            BlogIndexPage.objects.child_of(self).live().public().first()
        )
        return context
