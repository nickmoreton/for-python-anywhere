from datetime import date

from wagtail.models import Page, Site
from wagtail.test.utils import WagtailPageTestCase

from app.blog.models import BlogIndexPage, BlogPostPage
from app.home.models import HomePage


class BlogPageRenderingTests(WagtailPageTestCase):
    def setUp(self):
        root_page = Page.get_first_root_node()
        self.homepage = HomePage(title="Home", slug="blog-pages-home")
        root_page.add_child(instance=self.homepage)
        Site.objects.create(
            hostname="blog-pages.test",
            root_page=self.homepage,
            is_default_site=True,
        )
        self.blog_index = BlogIndexPage(title="Blog", slug="blog")
        self.homepage.add_child(instance=self.blog_index)
        self.blog_index.save_revision().publish()

    def create_post(self, **overrides):
        values = {
            "title": "A structured Wagtail post",
            "slug": "structured-post",
            "date": date(2026, 7, 18),
            "author_name": "Morgan Finch",
            "intro": "A concise introduction.",
            "body": [
                ("heading", "Compose with blocks"),
                (
                    "paragraph",
                    "<p>StreamField keeps content structured.</p>",
                ),
                ("bulleted_list", ["Flexible", "Searchable"]),
                (
                    "quote",
                    {
                        "text": "Structure supports editors.",
                        "attribution": "Morgan Finch",
                    },
                ),
                (
                    "code",
                    {
                        "language": "python",
                        "code": "class ArticlePage(Page):\n    pass",
                    },
                ),
            ],
        }
        values.update(overrides)
        post = BlogPostPage(**values)
        self.blog_index.add_child(instance=post)
        post.save_revision().publish()
        return post

    def test_index_renders_empty_state(self):
        response = self.client.get(self.blog_index.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "blog/blog_index_page.html")
        self.assertContains(response, "Stories are taking shape")
        self.assertContains(response, 'class="blog-shell"')

    def test_post_renders_all_supported_blocks(self):
        post = self.create_post()

        response = self.client.get(post.url)

        self.assertTemplateUsed(response, "blog/blog_post_page.html")
        self.assertContains(response, "18 July 2026")
        self.assertContains(response, "Morgan Finch")
        self.assertContains(response, "Compose with blocks")
        self.assertContains(response, 'class="article-shell"')
        self.assertContains(response, 'class="article__body"')
        self.assertContains(
            response,
            'class="article-block article-block--code"',
        )
        self.assertContains(
            response,
            '<ul class="article-block article-block--list">',
            html=False,
        )
        self.assertContains(response, "<blockquote", html=False)
        self.assertContains(response, "<code", html=False)

    def test_index_lists_published_post_as_an_article_card(self):
        self.create_post(
            title="Listed post",
            slug="listed-post",
            intro="Visible on the index.",
        )

        response = self.client.get(self.blog_index.url)

        self.assertContains(response, "blog-card")
        self.assertContains(response, 'class="blog-grid"')
        self.assertContains(response, "Listed post")
        self.assertContains(response, "Visible on the index.")
