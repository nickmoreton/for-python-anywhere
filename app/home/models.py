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
        from app.blog.models import BlogIndexPage, BlogPostPage

        context = super().get_context(request, *args, **kwargs)
        blog_page = (
            BlogIndexPage.objects.child_of(self).live().public().first()
        )
        featured_post = None
        latest_posts = BlogPostPage.objects.none()

        if blog_page:
            eligible_posts = blog_page.get_posts()
            if self.featured_post_id:
                featured_post = eligible_posts.filter(
                    pk=self.featured_post_id
                ).first()
            latest_posts = eligible_posts.exclude(
                pk=self.featured_post_id
            )[:3]

        context.update(
            {
                "blog_page": blog_page,
                "featured_post": featured_post,
                "latest_posts": latest_posts,
            }
        )
        return context
