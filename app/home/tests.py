from urllib.parse import urlparse

from app.home.models import HomePage

from wagtail.models import Page, Site
from wagtail.test.utils import WagtailPageTestCase


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

    def test_homepage_renders_placeholder_content(self):
        response = self.client.get(self.homepage.url)

        self.assertContains(response, "Something new is taking shape")
        self.assertContains(response, "Site preparation in progress")
        self.assertContains(response, "Powered by Wagtail")
        self.assertContains(response, "data-status-message")

    def test_homepage_does_not_render_generated_welcome_content(self):
        response = self.client.get(self.homepage.url)

        self.assertNotContains(response, "Welcome to your new Wagtail site!")
        self.assertNotContains(response, "css/welcome_page.css")

    def test_homepage_links_to_live_blog(self):
        from app.blog.models import BlogIndexPage

        blog = BlogIndexPage(title="Blog", slug="blog")
        self.homepage.add_child(instance=blog)
        blog.save_revision().publish()

        response = self.client.get(self.homepage.url)

        self.assertContains(response, "Read the blog")
        self.assertContains(response, urlparse(blog.url).path)

    def test_homepage_omits_blog_link_without_live_blog(self):
        response = self.client.get(self.homepage.url)

        self.assertNotContains(response, "Read the blog")
