from datetime import date, timedelta

from django.core.exceptions import ValidationError

from wagtail.models import Page, Site
from wagtail.test.utils import WagtailPageTestCase

from app.blog.models import BlogIndexPage, BlogPostPage
from app.home.models import HomePage


class BlogPageModelTests(WagtailPageTestCase):
    def setUp(self):
        root_page = Page.get_first_root_node()
        self.homepage = HomePage(title="Home", slug="blog-test-home")
        root_page.add_child(instance=self.homepage)
        Site.objects.create(
            hostname="blog-models.test",
            root_page=self.homepage,
            is_default_site=True,
        )
        self.blog_index = BlogIndexPage(title="Blog", slug="blog")
        self.homepage.add_child(instance=self.blog_index)

    def create_post(self, title, slug, post_date, live=True):
        post = BlogPostPage(
            title=title,
            slug=slug,
            date=post_date,
            author_name="Morgan Finch",
            intro=f"Introduction for {title}.",
            body=[
                ("heading", "A useful heading"),
                ("paragraph", "<p>A useful paragraph.</p>"),
                ("bulleted_list", ["First", "Second"]),
                (
                    "quote",
                    {
                        "text": "Editors shape the story.",
                        "attribution": "Sample author",
                    },
                ),
                (
                    "code",
                    {
                        "language": "python",
                        "code": "from wagtail.models import Page",
                    },
                ),
            ],
            live=live,
        )
        self.blog_index.add_child(instance=post)
        return post

    def test_page_type_relationships_are_constrained(self):
        self.assertAllowedParentPageTypes(BlogIndexPage, {HomePage})
        self.assertAllowedSubpageTypes(BlogIndexPage, {BlogPostPage})
        self.assertAllowedParentPageTypes(BlogPostPage, {BlogIndexPage})
        self.assertAllowedSubpageTypes(BlogPostPage, set())

    def test_post_fields_are_required_except_featured_image(self):
        post = BlogPostPage(title="Incomplete", slug="incomplete")

        with self.assertRaises(ValidationError) as error:
            post.full_clean()

        self.assertIn("date", error.exception.message_dict)
        self.assertIn("author_name", error.exception.message_dict)
        self.assertIn("intro", error.exception.message_dict)
        self.assertIn("body", error.exception.message_dict)
        self.assertNotIn("featured_image", error.exception.message_dict)

    def test_body_exposes_only_the_approved_blocks(self):
        block_names = list(
            BlogPostPage._meta.get_field("body").stream_block.child_blocks
        )

        self.assertEqual(
            block_names,
            ["heading", "paragraph", "bulleted_list", "quote", "code"],
        )

    def test_get_posts_returns_live_posts_newest_first(self):
        older = self.create_post(
            "Older",
            "older",
            date.today() - timedelta(days=1),
        )
        newer = self.create_post("Newer", "newer", date.today())
        draft = self.create_post(
            "Draft",
            "draft",
            date.today() + timedelta(days=1),
            live=False,
        )

        self.assertEqual(list(self.blog_index.get_posts()), [newer, older])
        self.assertNotIn(draft, self.blog_index.get_posts())
