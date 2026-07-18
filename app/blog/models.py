from django.core.exceptions import ValidationError
from django.db import models

from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.search import index

from app.blog.blocks import CodeBlock, QuoteBlock


class BlogIndexPage(Page):
    parent_page_types = ["home.HomePage"]
    subpage_types = ["blog.BlogPostPage"]

    def get_posts(self):
        return (
            BlogPostPage.objects.child_of(self)
            .live()
            .public()
            .order_by("-date", "-first_published_at")
        )

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["posts"] = self.get_posts()
        return context


class BlogPostPage(Page):
    date = models.DateField("Post date")
    author_name = models.CharField(max_length=255)
    intro = models.TextField()
    featured_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    body = StreamField(
        [
            (
                "heading",
                blocks.CharBlock(
                    max_length=120,
                    form_classname="title",
                    template="blog/blocks/heading.html",
                ),
            ),
            (
                "paragraph",
                blocks.RichTextBlock(
                    features=["bold", "italic", "link"],
                    template="blog/blocks/paragraph.html",
                ),
            ),
            (
                "bulleted_list",
                blocks.ListBlock(
                    blocks.CharBlock(max_length=240),
                    template="blog/blocks/bulleted_list.html",
                ),
            ),
            ("quote", QuoteBlock()),
            ("code", CodeBlock()),
        ],
        use_json_field=True,
    )

    parent_page_types = ["blog.BlogIndexPage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("author_name"),
        FieldPanel("intro"),
        FieldPanel("featured_image"),
        FieldPanel("body"),
    ]

    search_fields = Page.search_fields + [
        index.SearchField("intro"),
        index.SearchField("body"),
    ]

    def clean(self):
        super().clean()
        if not self.body:
            raise ValidationError({"body": "This field cannot be blank."})
