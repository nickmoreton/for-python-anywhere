from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import CommandError, call_command
from django.test import override_settings

from wagtail.images import get_image_model
from wagtail.models import Page, Site
from wagtail.test.utils import WagtailPageTestCase

from app.blog.models import BlogIndexPage, BlogPostPage
from app.blog.sample_content import SAMPLE_POSTS
from app.home.models import HomePage


class PopulateBlogCommandTests(WagtailPageTestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_directory.name
        )
        self.settings_override.enable()
        root_page = Page.get_first_root_node()
        self.homepage = HomePage(title="Home", slug="blog-command-home")
        root_page.add_child(instance=self.homepage)
        Site.objects.update(is_default_site=False)
        self.site = Site.objects.create(
            hostname="populate-blog.test",
            root_page=self.homepage,
            is_default_site=True,
        )

    def tearDown(self):
        self.settings_override.disable()
        self.media_directory.cleanup()

    def run_command(self):
        output = StringIO()
        call_command("populate_blog", stdout=output)
        return output.getvalue()

    def test_first_run_creates_published_blog_posts_and_valid_images(self):
        output = self.run_command()

        blog_index = BlogIndexPage.objects.get(slug="blog")
        posts = BlogPostPage.objects.child_of(blog_index)
        images = get_image_model().objects.filter(title__startswith="Blog seed:")
        self.assertEqual(posts.count(), 20)
        self.assertEqual(posts.live().count(), 20)
        self.assertEqual(images.count(), 5)
        self.assertIn("Created 20 posts", output)
        for image in images:
            self.assertTrue(Path(image.file.path).is_file())
            self.assertEqual((image.width, image.height), (1200, 720))

    def test_second_run_does_not_duplicate_pages_or_images(self):
        self.run_command()

        second_output = self.run_command()

        self.assertEqual(BlogIndexPage.objects.filter(slug="blog").count(), 1)
        self.assertEqual(BlogPostPage.objects.count(), 20)
        self.assertEqual(
            get_image_model()
            .objects.filter(title__startswith="Blog seed:")
            .count(),
            5,
        )
        self.assertIn("Created 0 posts", second_output)
        self.assertIn("Updated 20 posts", second_output)

    def test_rerun_restores_canonical_seeded_content(self):
        self.run_command()
        post = BlogPostPage.objects.get(slug=SAMPLE_POSTS[0].slug)
        post.intro = "Changed by a test"
        post.save_revision().publish()

        self.run_command()

        post.refresh_from_db()
        self.assertEqual(post.intro, SAMPLE_POSTS[0].intro)

    def test_unrelated_editor_post_is_preserved(self):
        self.run_command()
        blog_index = BlogIndexPage.objects.get(slug="blog")
        editor_post = BlogPostPage(
            title="Editor's post",
            slug="editors-post",
            date=SAMPLE_POSTS[0].post_date,
            author_name="Site editor",
            intro="Keep this post.",
            body=[("paragraph", "<p>Independent content.</p>")],
        )
        blog_index.add_child(instance=editor_post)
        editor_post.save_revision().publish()

        self.run_command()

        self.assertTrue(
            BlogPostPage.objects.filter(slug="editors-post").exists()
        )
        self.assertEqual(BlogPostPage.objects.count(), 21)

    def test_invalid_default_site_root_raises_command_error(self):
        self.site.root_page = Page.get_first_root_node()
        self.site.save(update_fields=["root_page"])

        with self.assertRaisesMessage(
            CommandError,
            "default site's root page must be a HomePage",
        ):
            self.run_command()

        self.assertFalse(BlogIndexPage.objects.exists())
