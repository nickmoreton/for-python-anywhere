from datetime import date, timedelta
from urllib.parse import urlparse

from django.db import models
from django.test import RequestFactory
from django.utils.text import slugify
from wagtail.admin.panels import FieldPanel

from app.blog.models import BlogIndexPage, BlogPostPage
from app.home.models import HomePage

from wagtail.models import Page, PageViewRestriction, Site
from wagtail.test.utils import WagtailPageTestCase


class HomePageModelTests(WagtailPageTestCase):
    def test_featured_post_is_an_optional_blog_post_chooser(self):
        field = HomePage._meta.get_field("featured_post")

        self.assertIs(field.remote_field.model, BlogPostPage)
        self.assertTrue(field.null)
        self.assertTrue(field.blank)
        self.assertEqual(field.remote_field.on_delete, models.SET_NULL)
        self.assertTrue(
            any(
                isinstance(panel, FieldPanel)
                and panel.field_name == "featured_post"
                for panel in HomePage.content_panels
            )
        )


class HomePageContextTests(WagtailPageTestCase):
    def setUp(self):
        root_page = Page.get_first_root_node()
        self.homepage = HomePage(title="Home", slug="context-home")
        root_page.add_child(instance=self.homepage)
        Site.objects.create(
            hostname="homepage-context.test",
            root_page=self.homepage,
            is_default_site=True,
        )
        self.blog = BlogIndexPage(title="Blog", slug="blog")
        self.homepage.add_child(instance=self.blog)
        self.blog.save_revision().publish()
        self.request = RequestFactory().get("/")

    def create_post(self, title, days_ago=0):
        post = BlogPostPage(
            title=title,
            slug=slugify(title),
            date=date(2026, 7, 19) - timedelta(days=days_ago),
            author_name="Morgan Finch",
            intro=f"Introduction for {title}.",
            body=[("paragraph", f"<p>Body for {title}.</p>")],
        )
        self.blog.add_child(instance=post)
        post.save_revision().publish()
        return post

    def get_home_context(self):
        self.homepage.refresh_from_db()
        return self.homepage.get_context(self.request)

    def test_context_selects_feature_and_three_latest_distinct_posts(self):
        featured = self.create_post("Featured", days_ago=0)
        newest = self.create_post("Newest other", days_ago=1)
        second = self.create_post("Second other", days_ago=2)
        third = self.create_post("Third other", days_ago=3)
        self.create_post("Fourth other", days_ago=4)
        self.homepage.featured_post = featured
        self.homepage.save()

        context = self.get_home_context()

        self.assertEqual(context["blog_page"], self.blog)
        self.assertEqual(context["featured_post"], featured)
        self.assertEqual(
            list(context["latest_posts"]),
            [newest, second, third],
        )

    def test_context_uses_post_date_before_publication_time(self):
        older_date = self.create_post("Published later", days_ago=2)
        newer_date = self.create_post("Dated later", days_ago=1)

        context = self.get_home_context()

        self.assertEqual(
            list(context["latest_posts"]),
            [newer_date, older_date],
        )

    def test_context_breaks_equal_post_dates_by_latest_publication(self):
        published_first = self.create_post("Published first", days_ago=1)
        published_second = self.create_post("Published second", days_ago=1)

        context = self.get_home_context()

        self.assertEqual(
            list(context["latest_posts"]),
            [published_second, published_first],
        )

    def test_context_omits_unpublished_selected_feature(self):
        featured = self.create_post("Unpublished feature")
        self.homepage.featured_post = featured
        self.homepage.save()
        featured.unpublish()

        context = self.get_home_context()

        self.assertIsNone(context["featured_post"])

    def test_context_omits_private_posts(self):
        featured = self.create_post("Private feature")
        visible = self.create_post("Visible post", days_ago=1)
        self.homepage.featured_post = featured
        self.homepage.save()
        PageViewRestriction.objects.create(
            page=featured,
            restriction_type=PageViewRestriction.LOGIN,
        )

        context = self.get_home_context()

        self.assertIsNone(context["featured_post"])
        self.assertEqual(list(context["latest_posts"]), [visible])

    def test_context_omits_feature_from_another_blog(self):
        root_page = Page.get_first_root_node()
        other_home = HomePage(title="Other home", slug="other-home")
        root_page.add_child(instance=other_home)
        other_blog = BlogIndexPage(title="Other blog", slug="other-blog")
        other_home.add_child(instance=other_blog)
        other_blog.save_revision().publish()
        other_post = BlogPostPage(
            title="Other post",
            slug="other-post",
            date=date(2026, 7, 19),
            author_name="Morgan Finch",
            intro="From another blog.",
            body=[("paragraph", "<p>Other body.</p>")],
        )
        other_blog.add_child(instance=other_post)
        other_post.save_revision().publish()
        self.homepage.featured_post = other_post
        self.homepage.save()

        context = self.get_home_context()

        self.assertIsNone(context["featured_post"])
        self.assertEqual(list(context["latest_posts"]), [])

    def test_context_returns_empty_values_without_a_live_blog(self):
        self.blog.unpublish()

        context = self.get_home_context()

        self.assertIsNone(context["blog_page"])
        self.assertIsNone(context["featured_post"])
        self.assertEqual(list(context["latest_posts"]), [])


class HomeSetUpTests(WagtailPageTestCase):
    """
    Tests for basic page structure setup and HomePage creation.
    """

    def test_root_create(self):
        root_page = Page.objects.get(pk=1)
        self.assertIsNotNone(root_page)

    def test_homepage_create(self):
        root_page = Page.objects.get(pk=1)
        homepage = HomePage(title="Home")
        root_page.add_child(instance=homepage)
        self.assertTrue(HomePage.objects.filter(title="Home").exists())


class HomeTests(WagtailPageTestCase):
    """
    Tests for homepage functionality and rendering.
    """

    def setUp(self):
        """
        Create a homepage instance for testing.
        """
        root_page = Page.get_first_root_node()
        Site.objects.create(hostname="testsite", root_page=root_page, is_default_site=True)
        self.homepage = HomePage(title="Home")
        root_page.add_child(instance=self.homepage)

    def test_homepage_is_renderable(self):
        self.assertPageIsRenderable(self.homepage)

    def test_homepage_template_used(self):
        response = self.client.get(self.homepage.url)
        self.assertTemplateUsed(response, "home/home_page.html")

    def test_homepage_does_not_render_generated_welcome_content(self):
        response = self.client.get(self.homepage.url)

        self.assertNotContains(response, "Welcome to your new Wagtail site!")
        self.assertNotContains(response, "css/welcome_page.css")


class HomePageRenderingTests(WagtailPageTestCase):
    def setUp(self):
        root_page = Page.get_first_root_node()
        self.homepage = HomePage(title="Field Notes", slug="render-home")
        root_page.add_child(instance=self.homepage)
        Site.objects.create(
            hostname="homepage-rendering.test",
            root_page=self.homepage,
            is_default_site=True,
        )
        self.blog = BlogIndexPage(title="Blog", slug="blog")
        self.homepage.add_child(instance=self.blog)
        self.blog.save_revision().publish()

    def create_post(self, title, days_ago=0, author="Morgan Finch"):
        post = BlogPostPage(
            title=title,
            slug=slugify(title),
            date=date(2026, 7, 19) - timedelta(days=days_ago),
            author_name=author,
            intro=f"Introduction for {title}.",
            body=[("paragraph", f"<p>Body for {title}.</p>")],
        )
        self.blog.add_child(instance=post)
        post.save_revision().publish()
        return post

    def test_homepage_renders_feature_and_three_latest_posts(self):
        featured = self.create_post("Chosen feature")
        latest = [
            self.create_post("Latest one", days_ago=1),
            self.create_post("Latest two", days_ago=2),
            self.create_post("Latest three", days_ago=3),
        ]
        self.create_post("Not on homepage", days_ago=4)
        self.homepage.featured_post = featured
        self.homepage.save()

        response = self.client.get(self.homepage.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="home-shell"')
        self.assertContains(response, 'class="home-feature"')
        self.assertContains(response, "Chosen feature")
        self.assertContains(response, "Introduction for Chosen feature.")
        self.assertContains(response, "19 July 2026")
        self.assertContains(response, "Morgan Finch")
        self.assertContains(response, "home-feature__image--fallback")
        self.assertContains(response, 'class="home-grid"')
        for post in latest:
            self.assertContains(response, post.title)
        self.assertNotContains(response, "Not on homepage")
        self.assertContains(response, "View all posts")
        self.assertContains(response, urlparse(self.blog.url).path)

    def test_homepage_omits_feature_when_none_is_selected(self):
        self.create_post("Latest only")

        response = self.client.get(self.homepage.url)

        self.assertNotContains(response, 'class="home-feature"')
        self.assertContains(response, "Latest only")
        self.assertContains(response, 'class="home-latest"')

    def test_homepage_omits_post_sections_without_a_live_blog(self):
        self.blog.unpublish()

        response = self.client.get(self.homepage.url)

        self.assertNotContains(response, 'class="home-feature"')
        self.assertNotContains(response, 'class="home-latest"')
        self.assertNotContains(response, "View all posts")

    def test_homepage_removes_coming_soon_content(self):
        response = self.client.get(self.homepage.url)

        self.assertNotContains(response, "Something new is taking shape")
        self.assertNotContains(response, "Site preparation in progress")
        self.assertNotContains(response, "Powered by Wagtail")
        self.assertNotContains(response, "data-status-message")
