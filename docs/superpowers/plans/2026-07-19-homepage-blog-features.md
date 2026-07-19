# Homepage Blog Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the temporary homepage with an editor-selected featured blog post and the three latest distinct blog posts.

**Architecture:** Store the editorial selection as an optional `HomePage.featured_post` relationship to `BlogPostPage`. Build all public post selections in `HomePage.get_context()` from the homepage's live, public child `BlogIndexPage`, then render those values in a semantic responsive template styled by the existing homepage Sass module.

**Tech Stack:** Python 3.13, Django 6.0, Wagtail 7.4, Django templates, Sass, vanilla JavaScript asset pipeline, Django/Wagtail test framework, MySQL.

## Global Constraints

- The featured post is selected by an editor on `HomePage`; there is no automatic fallback.
- The featured post must be live, public, and a direct child of this homepage's live, public blog index.
- `latest_posts` contains at most three live, public posts ordered by `-date`, then `-first_published_at`, and excludes the selected featured post.
- Replace the coming-soon presentation; do not add a page builder, carousel, new JavaScript interaction, framework, or frontend dependency.
- Keep source Sass in `assets/scss/pages/_home.scss`; never edit generated files under `app/static/`.
- Preserve graceful rendering when the blog, feature selection, images, or enough latest posts are missing.
- Use the commands documented in `AGENTS.md`; do not invent lint, type-check, or coverage commands.

---

## File Map

- `app/home/models.py`: owns the editable feature relationship and homepage context selection.
- `app/home/migrations/0003_homepage_featured_post.py`: adds the nullable database relationship.
- `app/home/tests.py`: verifies field configuration, context rules, fallbacks, and rendered homepage behavior.
- `app/home/templates/home/home_page.html`: renders the masthead, featured article, latest cards, and blog-index link.
- `assets/scss/pages/_home.scss`: owns the responsive homepage presentation.

No `AGENTS.md` update is required because this work does not change the documented project structure, commands, dependency management, runtime configuration, or workflows.

### Task 1: Add the editor-selected featured-post field

**Files:**
- Modify: `app/home/models.py`
- Create: `app/home/migrations/0003_homepage_featured_post.py`
- Test: `app/home/tests.py`

**Interfaces:**
- Consumes: the existing `blog.BlogPostPage` page type.
- Produces: `HomePage.featured_post: BlogPostPage | None` and `HomePage.featured_post_id: int | None`.

- [ ] **Step 1: Write the failing model-field test**

Add these imports and test to `app/home/tests.py`:

```python
from django.db import models
from wagtail.admin.panels import FieldPanel

from app.blog.models import BlogPostPage


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
```

- [ ] **Step 2: Run the focused test and verify the missing field fails**

Run:

```bash
uv run python manage.py test app.home.tests.HomePageModelTests.test_featured_post_is_an_optional_blog_post_chooser
```

Expected: `ERROR` with `HomePage has no field named 'featured_post'`.

- [ ] **Step 3: Add the model relationship and editor panel**

Change `app/home/models.py` to begin as follows, retaining the existing `get_context()` temporarily:

```python
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
```

Use no reverse relationship because the homepage is the only consumer; do not add any other homepage fields.

- [ ] **Step 4: Generate and inspect the migration**

Run:

```bash
uv run python manage.py makemigrations home
```

Expected: Django creates `app/home/migrations/0003_homepage_featured_post.py` with dependencies on `blog.0001_initial` and `home.0002_create_homepage`, and one `AddField` operation equivalent to:

```python
migrations.AddField(
    model_name="homepage",
    name="featured_post",
    field=models.ForeignKey(
        blank=True,
        null=True,
        on_delete=django.db.models.deletion.SET_NULL,
        related_name="+",
        to="blog.blogpostpage",
    ),
)
```

Review the generated file; do not hand-edit its generated timestamp or dependency names unless Django generated an incorrect graph.

- [ ] **Step 5: Run the model-field test**

Run:

```bash
uv run python manage.py test app.home.tests.HomePageModelTests
```

Expected: `OK` with one passing test.

- [ ] **Step 6: Check migration drift**

Run:

```bash
uv run python manage.py makemigrations --check --dry-run
```

Expected: `No changes detected`.

- [ ] **Step 7: Commit the editorial model**

```bash
git add app/home/models.py app/home/migrations/0003_homepage_featured_post.py app/home/tests.py
git commit -m "Add homepage featured post selection"
```

### Task 2: Select eligible featured and latest posts in homepage context

**Files:**
- Modify: `app/home/models.py`
- Modify: `app/home/tests.py`

**Interfaces:**
- Consumes: `BlogIndexPage.get_posts() -> PageQuerySet[BlogPostPage]`, `HomePage.featured_post_id`.
- Produces context keys `blog_page: BlogIndexPage | None`, `featured_post: BlogPostPage | None`, and `latest_posts: PageQuerySet[BlogPostPage]` containing zero to three items.

- [ ] **Step 1: Add reusable test content helpers**

Add these imports to `app/home/tests.py`:

```python
from datetime import date, timedelta

from django.test import RequestFactory
from django.utils.text import slugify
from wagtail.models import PageViewRestriction

from app.blog.models import BlogIndexPage, BlogPostPage
```

Add this test class after `HomePageModelTests`:

```python
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
```

- [ ] **Step 2: Write failing selection and ordering tests**

Add these tests to `HomePageContextTests`:

```python
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
```

- [ ] **Step 3: Write failing eligibility and fallback tests**

Add these tests to `HomePageContextTests`:

```python
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
```

- [ ] **Step 4: Run the context tests and verify missing keys fail**

Run:

```bash
uv run python manage.py test app.home.tests.HomePageContextTests
```

Expected: failures or errors because the current context has no `featured_post` or `latest_posts` keys.

- [ ] **Step 5: Implement the minimal context selection**

Replace `HomePage.get_context()` in `app/home/models.py` with:

```python
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
```

The query always excludes the selected identifier. If that selection is unavailable or belongs elsewhere, it is absent from `eligible_posts` already, so no eligible local post is lost.

- [ ] **Step 6: Run the context and existing blog model tests**

Run:

```bash
uv run python manage.py test app.home.tests.HomePageContextTests app.blog.tests.test_models
```

Expected: all tests pass.

- [ ] **Step 7: Commit context selection**

```bash
git add app/home/models.py app/home/tests.py
git commit -m "Select homepage blog content"
```

### Task 3: Render the expanded homepage

**Files:**
- Modify: `app/home/templates/home/home_page.html`
- Modify: `app/home/tests.py`

**Interfaces:**
- Consumes: template context `blog_page`, `featured_post`, and `latest_posts` from Task 2.
- Produces: semantic class hooks `.home-shell`, `.home-masthead`, `.home-feature`, `.home-latest`, `.home-grid`, and `.home-card` for Task 4.

- [ ] **Step 1: Replace placeholder assertions with failing editorial rendering tests**

In `HomeTests`, replace `test_homepage_renders_placeholder_content`, `test_homepage_links_to_live_blog`, and `test_homepage_omits_blog_link_without_live_blog` with a separate rendering class. Keep the setup/renderability/template tests that do not assert retired copy. Add:

```python
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
```

- [ ] **Step 2: Run rendering tests and verify the old template fails them**

Run:

```bash
uv run python manage.py test app.home.tests.HomePageRenderingTests
```

Expected: failures for missing `.home-shell`, featured/latest content, and “View all posts”.

- [ ] **Step 3: Replace the homepage template**

Replace `app/home/templates/home/home_page.html` with:

```django
{% extends "base.html" %}
{% load wagtailcore_tags wagtailimages_tags %}

{% block body_class %}template-homepage{% endblock %}

{% block content %}
<main class="home-shell">
    <header class="home-masthead">
        <p class="home-masthead__brand">{{ page.title }}</p>
        <p class="home-masthead__eyebrow">Notes from the build</p>
        <h1>Thoughtful publishing, built in the open</h1>
        <p class="home-masthead__intro">
            Practical stories about Wagtail, thoughtful publishing, and the web.
        </p>
    </header>

    {% if featured_post %}
    <article class="home-feature" aria-labelledby="featured-post-title">
        <a class="home-feature__image-link" href="{% pageurl featured_post %}" tabindex="-1" aria-hidden="true">
            {% if featured_post.featured_image %}
                {% image featured_post.featured_image fill-1200x760 loading="eager" class="home-feature__image" alt="" %}
            {% else %}
                <span class="home-feature__image home-feature__image--fallback"></span>
            {% endif %}
        </a>
        <div class="home-feature__body">
            <p class="home-feature__eyebrow">Featured post</p>
            <p class="home-feature__meta">
                <time datetime="{{ featured_post.date|date:'Y-m-d' }}">{{ featured_post.date|date:"j F Y" }}</time>
                · {{ featured_post.author_name }}
            </p>
            <h2 id="featured-post-title"><a href="{% pageurl featured_post %}">{{ featured_post.title }}</a></h2>
            <p class="home-feature__intro">{{ featured_post.intro }}</p>
            <p class="home-feature__action"><a class="button-link" href="{% pageurl featured_post %}">Read the featured post</a></p>
        </div>
    </article>
    {% endif %}

    {% if latest_posts %}
    <section class="home-latest" aria-labelledby="latest-posts-title">
        <div class="home-latest__heading">
            <div>
                <p class="home-latest__eyebrow">From the blog</p>
                <h2 id="latest-posts-title">Latest posts</h2>
            </div>
            {% if blog_page %}
            <a class="home-latest__all" href="{% pageurl blog_page %}">View all posts</a>
            {% endif %}
        </div>
        <div class="home-grid">
            {% for post in latest_posts %}
            <article class="home-card">
                <a class="home-card__image-link" href="{% pageurl post %}" tabindex="-1" aria-hidden="true">
                    {% if post.featured_image %}
                        {% image post.featured_image fill-720x432 loading="lazy" class="home-card__image" alt="" %}
                    {% else %}
                        <span class="home-card__image home-card__image--fallback"></span>
                    {% endif %}
                </a>
                <div class="home-card__body">
                    <p class="home-card__meta">
                        <time datetime="{{ post.date|date:'Y-m-d' }}">{{ post.date|date:"j F Y" }}</time>
                        · {{ post.author_name }}
                    </p>
                    <h3><a href="{% pageurl post %}">{{ post.title }}</a></h3>
                    <p>{{ post.intro }}</p>
                </div>
            </article>
            {% endfor %}
        </div>
    </section>
    {% elif blog_page %}
    <p class="home-blog-link"><a class="button-link" href="{% pageurl blog_page %}">View all posts</a></p>
    {% endif %}
</main>
{% endblock content %}
```

The `elif` preserves access to an empty blog index without inventing an empty-state card. When latest posts exist, the full-blog link is part of that section heading.

- [ ] **Step 4: Run homepage rendering tests**

Run:

```bash
uv run python manage.py test app.home.tests.HomePageRenderingTests app.home.tests.HomeTests
```

Expected: all tests pass.

- [ ] **Step 5: Commit the semantic homepage**

```bash
git add app/home/templates/home/home_page.html app/home/tests.py
git commit -m "Render featured and latest homepage posts"
```

### Task 4: Style and verify the responsive homepage

**Files:**
- Modify: `assets/scss/pages/_home.scss`

**Interfaces:**
- Consumes: the `.home-*` template class hooks from Task 3 and existing `mixins`/`tokens` Sass APIs.
- Produces: a responsive wide feature, three-card grid, fallbacks, and visible keyboard focus without changing the Sass manifest.

- [ ] **Step 1: Replace retired coming-soon Sass with homepage layout styles**

Replace `assets/scss/pages/_home.scss` with:

```scss
@use "../abstracts/mixins";
@use "../abstracts/tokens";

.home-shell {
  @include mixins.page-shell;
}

.home-masthead {
  max-width: 56rem;
  margin-bottom: clamp(2.5rem, 7vw, 6rem);
}

.home-masthead__brand,
.home-masthead__eyebrow,
.home-feature__eyebrow,
.home-latest__eyebrow {
  @include mixins.uppercase-label;
}

.home-masthead__brand {
  margin: 0 0 clamp(2rem, 6vw, 4rem);
}

.home-masthead__eyebrow,
.home-feature__eyebrow,
.home-latest__eyebrow {
  margin: 0 0 0.75rem;
  color: tokens.$accent;
}

.home-masthead h1 {
  @include mixins.display-heading;

  max-width: 14ch;
  margin: 0 0 1.25rem;
  font-size: clamp(2.7rem, 8vw, 5.8rem);
}

.home-masthead__intro {
  @include mixins.supporting-copy;

  max-width: 42rem;
  margin: 0;
  font-size: clamp(1.05rem, 2vw, 1.3rem);
}

.home-feature,
.home-card {
  overflow: hidden;
  border: 1px solid rgba(tokens.$line, 0.95);
  border-radius: 1.25rem;
  background: rgba(tokens.$surface, 0.94);
  box-shadow: 0 1rem 3rem rgba(tokens.$ink, 0.06);
}

.home-feature {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(18rem, 0.75fr);
  margin-bottom: clamp(3.5rem, 8vw, 7rem);
}

.home-feature__image-link,
.home-card__image-link {
  display: block;
  background: tokens.$accent-soft;
}

.home-feature__image,
.home-card__image {
  display: block;
  width: 100%;
  object-fit: cover;
}

.home-feature__image {
  height: 100%;
  min-height: 30rem;
}

.home-feature__body {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: clamp(2rem, 5vw, 4rem);
}

.home-feature__meta,
.home-card__meta {
  margin: 0 0 0.75rem;
  color: tokens.$muted;
  font-size: 0.78rem;
}

.home-feature h2 {
  margin: 0 0 1rem;
  font-size: clamp(2rem, 4vw, 3.6rem);
  line-height: 1.02;
}

.home-feature h2 a,
.home-card h3 a {
  text-decoration: none;
}

.home-feature__intro {
  margin: 0 0 1.75rem;
  color: tokens.$muted;
}

.home-feature__action {
  margin: 0;
}

.home-feature__image--fallback,
.home-card__image--fallback {
  background:
    radial-gradient(
      circle at 25% 30%,
      rgba(tokens.$surface, 0.8) 0 8%,
      transparent 9%
    ),
    linear-gradient(135deg, tokens.$accent-soft, rgba(tokens.$accent, 0.72));
}

.home-latest__heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
}

.home-latest h2 {
  margin: 0;
  font-size: clamp(2rem, 5vw, 3.4rem);
  line-height: 1.05;
}

.home-latest__all {
  flex: 0 0 auto;
  font-weight: 700;
}

.home-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 19rem), 1fr));
  gap: 1.5rem;
}

.home-card__image {
  aspect-ratio: 5 / 3;
}

.home-card__body {
  padding: 1.5rem;
}

.home-card h3 {
  margin: 0 0 0.75rem;
  font-size: clamp(1.35rem, 3vw, 1.8rem);
  line-height: 1.15;
}

.home-card__body > p:last-child {
  margin-bottom: 0;
  color: tokens.$muted;
}

.home-blog-link {
  margin: 0;
}

.home-shell a:focus-visible {
  @include mixins.focus-ring;
}

@media (max-width: 52rem) {
  .home-feature {
    grid-template-columns: 1fr;
  }

  .home-feature__image {
    min-height: 0;
    aspect-ratio: 16 / 9;
  }
}

@media (max-width: tokens.$narrow-breakpoint) {
  .home-shell {
    width: min(100% - 1.5rem, 76rem);
  }

  .home-feature,
  .home-card {
    border-radius: 1rem;
  }

  .home-latest__heading {
    align-items: start;
    flex-direction: column;
  }
}
```

- [ ] **Step 2: Build and test the locked frontend pipeline**

Run:

```bash
npm run build
npm test
bash scripts/test-asset-pipeline.sh
```

Expected: Sass and esbuild finish without errors, Node tests pass, and the script ends with `PASS: asset pipeline`. Generated `app/static/css/app.css` and `app/static/js/app.js` remain ignored and must not be staged.

- [ ] **Step 3: Run the complete backend verification suite**

Run:

```bash
uv run python manage.py test
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Expected: all Django/Wagtail tests pass, `System check identified no issues`, and `No changes detected`.

- [ ] **Step 4: Inspect the final diff and repository state**

Run:

```bash
git diff --check
git status --short
git diff --stat HEAD
```

Expected: no whitespace errors; only `assets/scss/pages/_home.scss` is uncommitted at this task boundary, and ignored generated assets do not appear.

- [ ] **Step 5: Commit the responsive presentation**

```bash
git add assets/scss/pages/_home.scss
git commit -m "Style expanded editorial homepage"
```

- [ ] **Step 6: Confirm the branch is clean and contains the planned commits**

Run:

```bash
git status --short
git log --oneline --decorate main..HEAD
```

Expected: clean status and commits for the approved design, editorial field, context selection, semantic template, and responsive styles.
