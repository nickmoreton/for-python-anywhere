# Wagtail Blog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a native Wagtail blog at `/blog/` and a rerunnable command that publishes 20 original, fact-grounded Wagtail sample posts with deterministic local artwork.

**Architecture:** A new `app.blog` application owns a constrained `BlogIndexPage` / `BlogPostPage` tree, focused StreamField blocks, public templates, immutable seed content, deterministic image generation, and the population command. `HomePage` discovers its live blog child for navigation, while the existing Sass bundle supplies the visual system. Stable slugs and seed-image titles make the command convergent without deleting editor content.

**Tech Stack:** Python 3.13, Django 6, Wagtail 7.4, MySQL, Pillow through Wagtail, Django management commands, Sass, vanilla JavaScript, UV, Node 24.18.0.

## Global Constraints

- Run commands from the repository root beside `manage.py`.
- Keep `/` as the current coming-soon homepage and place the blog at `/blog/`.
- Use Wagtail pages and StreamField, not ordinary Django article models.
- Post fields are `date`, `author_name`, `intro`, optional `featured_image`, and required `body`.
- Body blocks are heading, paragraph, bulleted list, quote, and code only.
- Do not add pagination, categories, tags, RSS, comments, profiles, related posts, or JavaScript interactions.
- The sample command makes no network requests and copies no external articles.
- Sample copy is original, uses fictional authors, and is verified from first-party Wagtail sources.
- Artwork is deterministic PNG media generated at runtime and is never committed.
- Preserve the Sass/esbuild pipeline; never edit generated static files directly.
- Do not add dependencies or alter deployment behavior.
- Preserve unrelated working-tree changes.

## File Map

- `app/blog/blocks.py`: quote and code block structures.
- `app/blog/models.py`: page models, constraints, panels, search, and listing query.
- `app/blog/templates/blog/`: listing, detail, and block templates.
- `app/blog/sample_content.py`: immutable canonical content for 20 posts.
- `app/blog/sample_images.py`: pure deterministic PNG generator.
- `app/blog/management/commands/populate_blog.py`: validation and idempotent database/media writes.
- `app/blog/tests/`: focused model, page, sample-data, and command tests.
- `app/settings/base.py`: blog app registration.
- `app/home/models.py`, `app/home/templates/home/home_page.html`, `app/home/tests.py`: homepage blog discovery, link, and tests.
- `assets/scss/app.scss`: blog styles using existing tokens.
- `AGENTS.md`: structure and command documentation.

---

### Task 1: Page Models and Migration

**Files:**
- Create: `app/blog/__init__.py`
- Create: `app/blog/apps.py`
- Create: `app/blog/blocks.py`
- Create: `app/blog/models.py`
- Create: `app/blog/migrations/__init__.py`
- Create: `app/blog/tests/__init__.py`
- Create: `app/blog/tests/test_models.py`
- Create: `app/blog/migrations/0001_initial.py` through `makemigrations`
- Modify: `app/settings/base.py`

**Interfaces:**
- Produces: `BlogIndexPage.get_posts()`, `BlogIndexPage` context key `posts`, and all `BlogPostPage` fields consumed later.

- [ ] **Step 1: Write failing tests**

Create `test_models.py` using `WagtailPageTestCase`. Build `Page` root → `HomePage` → `BlogIndexPage`, then assert:

```python
self.assertAllowedParentPageTypes(BlogIndexPage, {HomePage})
self.assertAllowedSubpageTypes(BlogIndexPage, {BlogPostPage})
self.assertAllowedParentPageTypes(BlogPostPage, {BlogIndexPage})
self.assertAllowedSubpageTypes(BlogPostPage, set())

block_names = list(BlogPostPage._meta.get_field("body").stream_block.child_blocks)
self.assertEqual(block_names, ["heading", "paragraph", "bulleted_list", "quote", "code"])
```

Create two live posts and one draft, then assert `list(index.get_posts())` contains only the live posts ordered by `-date`, then `-first_published_at`. Call `full_clean()` on a post without content and assert `date`, `author_name`, `intro`, and `body` fail while `featured_image` does not.

- [ ] **Step 2: Verify red**

Run `uv run python manage.py test app.blog.tests.test_models`.

Expected: FAIL because `app.blog.models` does not exist.

- [ ] **Step 3: Implement the app and blocks**

Create `apps.py`:

```python
from django.apps import AppConfig


class BlogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.blog"
```

Create `blocks.py`:

```python
from wagtail import blocks


class QuoteBlock(blocks.StructBlock):
    text = blocks.TextBlock(required=True)
    attribution = blocks.CharBlock(required=False, max_length=120)

    class Meta:
        icon = "openquote"
        template = "blog/blocks/quote.html"


class CodeBlock(blocks.StructBlock):
    language = blocks.CharBlock(required=False, max_length=40)
    code = blocks.TextBlock(required=True)

    class Meta:
        icon = "code"
        template = "blog/blocks/code.html"
```

- [ ] **Step 4: Implement page models**

Create `models.py`:

```python
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
        return BlogPostPage.objects.child_of(self).live().public().order_by(
            "-date", "-first_published_at"
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
        "wagtailimages.Image", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    body = StreamField([
        ("heading", blocks.CharBlock(max_length=120, form_classname="title", template="blog/blocks/heading.html")),
        ("paragraph", blocks.RichTextBlock(features=["bold", "italic", "link"], template="blog/blocks/paragraph.html")),
        ("bulleted_list", blocks.ListBlock(blocks.CharBlock(max_length=240), template="blog/blocks/bulleted_list.html")),
        ("quote", QuoteBlock()),
        ("code", CodeBlock()),
    ], use_json_field=True)

    parent_page_types = ["blog.BlogIndexPage"]
    subpage_types = []
    content_panels = Page.content_panels + [
        FieldPanel("date"), FieldPanel("author_name"), FieldPanel("intro"),
        FieldPanel("featured_image"), FieldPanel("body"),
    ]
    search_fields = Page.search_fields + [
        index.SearchField("intro"), index.SearchField("body"),
    ]
```

Register `"app.blog"` immediately after `"app.home"` in `INSTALLED_APPS`.

- [ ] **Step 5: Generate, review, and test migration**

Run:

```bash
uv run python manage.py makemigrations blog
uv run python manage.py test app.blog.tests.test_models
uv run python manage.py makemigrations --check --dry-run
```

Expected: `0001_initial.py` creates both page models and the five post fields; tests pass; drift check prints `No changes detected`.

- [ ] **Step 6: Commit**

```bash
git add app/blog app/settings/base.py
git commit -m "feat: add Wagtail blog page models"
```

---

### Task 2: Public Rendering and Homepage Link

**Files:**
- Create: `app/blog/templates/blog/blog_index_page.html`
- Create: `app/blog/templates/blog/blog_post_page.html`
- Create: `app/blog/templates/blog/blocks/{heading,paragraph,bulleted_list,quote,code}.html`
- Create: `app/blog/tests/test_pages.py`
- Modify: `app/home/models.py`
- Modify: `app/home/templates/home/home_page.html`
- Modify: `app/home/tests.py`

**Interfaces:**
- Consumes: Task 1 page fields and `posts` context.
- Produces: homepage `blog_page` context and CSS class contract for Task 3.

- [ ] **Step 1: Write failing rendering tests**

Use `WagtailPageTestCase` to create and publish the page tree. Assert the empty index contains `Stories are taking shape`. Create a post containing every block and assert its response contains `18 July 2026`, author, `<ul class="article-block article-block--list">`, `<blockquote`, and `<code`. Assert a populated index contains `blog-card`, title, and intro. Add homepage tests asserting a live blog renders `Read the blog` and its URL, while no live blog omits the action.

- [ ] **Step 2: Verify red**

Run `uv run python manage.py test app.blog.tests.test_pages app.home.tests.HomeTests`.

Expected: FAIL on missing templates and missing homepage context.

- [ ] **Step 3: Add homepage discovery**

Implement inside `HomePage`:

```python
def get_context(self, request, *args, **kwargs):
    from app.blog.models import BlogIndexPage

    context = super().get_context(request, *args, **kwargs)
    context["blog_page"] = BlogIndexPage.objects.child_of(self).live().public().first()
    return context
```

Load `wagtailcore_tags` in the homepage template and add after the intro:

```django
{% if blog_page %}
<p class="coming-soon__actions">
    <a class="button-link" href="{% pageurl blog_page %}">Read the blog</a>
</p>
{% endif %}
```

- [ ] **Step 4: Add templates**

The index extends `base.html`, loads `wagtailcore_tags wagtailimages_tags`, and renders:

```django
<main class="blog-shell">
  <header class="blog-masthead">
    <a class="blog-masthead__brand" href="{% pageurl page.get_parent %}">{{ page.get_parent.title }}</a>
    <p class="blog-masthead__eyebrow">Notes from the build</p>
    <h1>{{ page.title }}</h1>
    <p class="blog-masthead__intro">Practical stories about Wagtail, thoughtful publishing, and the web.</p>
  </header>
  {% if posts %}<section class="blog-grid" aria-label="Blog posts">
  {% for post in posts %}<article class="blog-card">
    <a class="blog-card__image-link" href="{% pageurl post %}" tabindex="-1" aria-hidden="true">
    {% if post.featured_image %}{% image post.featured_image fill-720x432 loading="lazy" class="blog-card__image" alt="" %}
    {% else %}<span class="blog-card__image blog-card__image--fallback"></span>{% endif %}</a>
    <div class="blog-card__body"><p class="blog-card__meta"><time datetime="{{ post.date|date:'Y-m-d' }}">{{ post.date|date:"j F Y" }}</time> · {{ post.author_name }}</p>
    <h2><a href="{% pageurl post %}">{{ post.title }}</a></h2><p>{{ post.intro }}</p></div>
  </article>{% endfor %}</section>
  {% else %}<section class="blog-empty"><p class="blog-empty__eyebrow">Please check back soon</p><h2>Stories are taking shape</h2><p>The first article is still being carefully prepared.</p></section>{% endif %}
</main>
```

The detail extends `base.html`, loads the same tags, and renders:

```django
<main class="article-shell"><article class="article">
  <header class="article__header"><a class="article__back" href="{% pageurl page.get_parent %}">Back to {{ page.get_parent.title }}</a>
  <p class="article__meta"><time datetime="{{ page.date|date:'Y-m-d' }}">{{ page.date|date:"j F Y" }}</time> · {{ page.author_name }}</p>
  <h1>{{ page.title }}</h1><p class="article__intro">{{ page.intro }}</p></header>
  {% if page.featured_image %}<figure class="article__hero">{% image page.featured_image width-1200 loading="eager" alt="" %}</figure>{% endif %}
  <div class="article__body">{% for block in page.body %}{% include_block block %}{% endfor %}</div>
</article></main>
```

Create block templates with these exact semantic outputs:

```django
{# heading.html #}<h2 class="article-block article-block--heading">{{ value }}</h2>
{# paragraph.html #}<div class="article-block article-block--paragraph">{{ value|richtext }}</div>
{# bulleted_list.html #}<ul class="article-block article-block--list">{% for item in value %}<li>{{ item }}</li>{% endfor %}</ul>
{# quote.html #}<blockquote class="article-block article-block--quote"><p>{{ value.text }}</p>{% if value.attribution %}<footer>— {{ value.attribution }}</footer>{% endif %}</blockquote>
{# code.html #}<div class="article-block article-block--code">{% if value.language %}<p class="article-block__language">{{ value.language }}</p>{% endif %}<pre><code>{{ value.code }}</code></pre></div>
```

The comments name target files and are not included in them.

- [ ] **Step 5: Verify green and commit**

```bash
uv run python manage.py test app.blog.tests.test_pages app.home.tests.HomeTests
git add app/blog/templates app/blog/tests/test_pages.py app/home/models.py app/home/templates/home/home_page.html app/home/tests.py
git commit -m "feat: render blog pages and homepage link"
```

Expected: focused tests pass.

---

### Task 3: Visual System

**Files:**
- Modify: `assets/scss/app.scss`
- Test: `app/blog/tests/test_pages.py`

**Interfaces:**
- Consumes: Task 2 class names.
- Produces: responsive compiled styling without new dependencies.

- [ ] **Step 1: Strengthen class-contract tests**

Assert the rendering responses contain `blog-shell`, `blog-grid`, `article-shell`, `article__body`, and `article-block--code`. Temporarily change one matching template class, run its test to prove failure, then restore it.

- [ ] **Step 2: Add Sass using existing tokens**

Add complete rules for:

```scss
.button-link { display: inline-flex; min-height: 2.75rem; padding: .65rem 1rem; border-radius: 999px; color: $surface; background: $accent; font-weight: 700; text-decoration: none; }
.button-link:hover { color: $surface; background: darken($accent, 8%); }
.button-link:focus-visible, .blog-masthead a:focus-visible, .blog-card a:focus-visible, .article a:focus-visible { outline: .2rem solid $accent; outline-offset: .22rem; }
.coming-soon__actions { margin: 0 0 1.5rem; }
.blog-shell, .article-shell { width: min(100% - 2.5rem, 76rem); margin-inline: auto; padding-block: clamp(2rem, 6vw, 5rem); }
.blog-masthead, .article__header { max-width: 52rem; margin-bottom: clamp(2.5rem, 6vw, 5rem); }
.blog-masthead__brand, .article__back { display: inline-block; margin-bottom: clamp(2rem, 6vw, 4rem); }
.blog-masthead__eyebrow, .blog-empty__eyebrow, .article__meta { color: $accent; font-size: .8rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
.blog-masthead h1, .article h1 { max-width: 14ch; margin: 0 0 1.25rem; font-size: clamp(2.7rem, 8vw, 5.8rem); font-weight: 600; letter-spacing: -.055em; line-height: .98; }
.blog-masthead__intro, .article__intro { max-width: 42rem; margin: 0; color: $muted; font-size: clamp(1.05rem, 2vw, 1.3rem); }
.blog-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 19rem), 1fr)); gap: 1.5rem; }
.blog-card, .blog-empty { overflow: hidden; border: 1px solid rgba($line, .95); border-radius: 1.25rem; background: rgba($surface, .94); box-shadow: 0 1rem 3rem rgba($ink, .06); }
.blog-card__image-link { display: block; background: $accent-soft; }
.blog-card__image { display: block; width: 100%; aspect-ratio: 5 / 3; object-fit: cover; }
.blog-card__image--fallback { background: radial-gradient(circle at 25% 30%, rgba($surface, .8) 0 8%, transparent 9%), linear-gradient(135deg, $accent-soft, rgba($accent, .72)); }
.blog-card__body, .blog-empty { padding: 1.5rem; }
.blog-card__meta { margin: 0 0 .7rem; color: $muted; font-size: .78rem; }
.blog-card h2 { margin: 0 0 .75rem; font-size: clamp(1.35rem, 3vw, 1.8rem); line-height: 1.15; }
.blog-card h2 a { text-decoration: none; }
.article { width: min(100%, 62rem); margin-inline: auto; }
.article__hero { margin: 0 0 clamp(2.5rem, 6vw, 5rem); }
.article__hero img { display: block; width: 100%; height: auto; border-radius: 1.25rem; }
.article__body { width: min(100%, 44rem); margin-inline: auto; font-size: 1.05rem; }
.article-block { margin-block: 0 1.5rem; }
.article-block--heading { margin-top: 2.7rem; font-size: clamp(1.6rem, 4vw, 2.3rem); line-height: 1.15; }
.article-block--list { padding-left: 1.4rem; }
.article-block--quote { margin-inline: 0; padding: 1.5rem; border-left: .3rem solid $accent; border-radius: 0 1rem 1rem 0; background: rgba($accent-soft, .55); }
.article-block--code { overflow: hidden; border-radius: 1rem; color: #eef5f0; background: $ink; }
.article-block__language { margin: 0; padding: .65rem 1rem; border-bottom: 1px solid rgba($surface, .16); color: rgba($surface, .75); font-size: .75rem; font-weight: 700; text-transform: uppercase; }
.article-block--code pre { overflow-x: auto; margin: 0; padding: 1.25rem; }
.article-block--code code { font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; font-size: .9rem; }
@media (max-width: 34rem) { .blog-shell, .article-shell { width: min(100% - 1.5rem, 76rem); } .blog-card, .blog-empty, .article__hero img { border-radius: 1rem; } }
```

- [ ] **Step 3: Build, test, and commit**

```bash
npm test
bash scripts/test-asset-pipeline.sh
rg -q 'blog-grid' app/static/css/app.css
rg -q 'article-block--code' app/static/css/app.css
uv run python manage.py test app.blog.tests.test_pages app.home.tests.HomeTests
git add assets/scss/app.scss app/blog/tests/test_pages.py
git commit -m "feat: style the public blog"
```

Expected: Node and Django tests pass, the asset script prints PASS, and generated static files remain ignored.

---

### Task 4: Canonical Content and Artwork

**Files:**
- Create: `app/blog/sample_content.py`
- Create: `app/blog/sample_images.py`
- Create: `app/blog/tests/test_sample_data.py`

**Interfaces:**
- Produces: immutable `SAMPLE_POSTS`, `SamplePost.stream_data()`, `IMAGE_PALETTES`, and `build_seed_png(key, title, palette_index)`.

- [ ] **Step 1: Write failing pure tests**

Assert exactly 20 unique slugs, every post has title/intro/fictional author/two or more fact statements, and `stream_data()` uses only approved blocks. Call `build_seed_png()` twice and assert identical bytes, filename `blog-seed-page-tree.png`, PNG format, and `(1200, 720)` size. Assert five palettes.

- [ ] **Step 2: Verify red**

Run `uv run python manage.py test app.blog.tests.test_sample_data`.

Expected: FAIL on missing modules.

- [ ] **Step 3: Implement sample data**

Use this exact interface:

```python
from dataclasses import dataclass
from datetime import date, timedelta

AUTHORS = ("Morgan Finch", "Avery Reed", "Rowan Hale", "Quinn Marsh")
BASE_DATE = date(2026, 7, 18)

@dataclass(frozen=True)
class SamplePost:
    title: str
    slug: str
    intro: str
    facts: tuple[str, ...]
    takeaway: str
    author_name: str
    days_ago: int
    code_language: str = ""
    code: str = ""

    @property
    def post_date(self):
        return BASE_DATE - timedelta(days=self.days_ago)

    def stream_data(self):
        result = [
            ("heading", "Why it matters"),
            ("paragraph", f"<p>{self.facts[0]}</p>"),
            ("heading", "What to keep in mind"),
            ("bulleted_list", list(self.facts[1:])),
            ("quote", {"text": self.takeaway, "attribution": self.author_name}),
        ]
        if self.code:
            result.append(("code", {"language": self.code_language, "code": self.code}))
        return result
```

Add a module docstring listing the first-party sources and check date `2026-07-18`. Define 20 explicit `SamplePost` entries with dates spaced three days apart, alternating authors, original intros, at least three verified fact statements each, a distinct takeaway, and optional short code examples only where they clarify an API. Use these exact title/slug pairs:

1. `Understanding Wagtail's page tree` / `understanding-wagtails-page-tree`
2. `Building flexible articles with StreamField` / `building-flexible-articles-with-streamfield`
3. `Choosing useful StreamField block boundaries` / `choosing-useful-streamfield-block-boundaries`
4. `Working with Wagtail image renditions` / `working-with-wagtail-image-renditions`
5. `Writing context-aware image alternative text` / `writing-context-aware-image-alternative-text`
6. `Previewing content before publication` / `previewing-content-before-publication`
7. `Revisions, drafts, and publishing` / `revisions-drafts-and-publishing`
8. `Organising reusable content with snippets` / `organising-reusable-content-with-snippets`
9. `Searching Wagtail content` / `searching-wagtail-content`
10. `Managing redirects after URL changes` / `managing-redirects-after-url-changes`
11. `Editorial workflows and moderation` / `editorial-workflows-and-moderation`
12. `Supporting multiple sites` / `supporting-multiple-sites`
13. `Localising content with Wagtail` / `localising-content-with-wagtail`
14. `Using Wagtail as a headless CMS` / `using-wagtail-as-a-headless-cms`
15. `Improving page performance with caching` / `improving-page-performance-with-caching`
16. `Prefetching image renditions efficiently` / `prefetching-image-renditions-efficiently`
17. `Testing page types with WagtailPageTestCase` / `testing-page-types-with-wagtailpagetestcase`
18. `Designing accessible editor-controlled content` / `designing-accessible-editor-controlled-content`
19. `Extending the Wagtail admin with hooks` / `extending-the-wagtail-admin-with-hooks`
20. `What Wagtail 7.4 LTS means for a project` / `what-wagtail-74-lts-means-for-a-project`

The fact set must cover page-tree routing, StreamField JSON blocks and validation, renditions and contextual alt text, preview/revisions/publishing, snippets, search, redirects, workflows, multi-site, localization, headless limitations, caching, rendition prefetch, `WagtailPageTestCase`, accessible modeling, hooks, and Wagtail 7.4 LTS. Do not paraphrase source sentences closely.

- [ ] **Step 4: Implement pure PNG generation**

```python
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw

IMAGE_PALETTES = (
    ("#dce9e1", "#356b52", "#202321"),
    ("#e7e0d5", "#8a5a35", "#202321"),
    ("#dce4ed", "#3f6385", "#202321"),
    ("#eadfe7", "#80536f", "#202321"),
    ("#e8e6cf", "#77713b", "#202321"),
)

def build_seed_png(key, title, palette_index):
    background, accent, ink = IMAGE_PALETTES[palette_index % len(IMAGE_PALETTES)]
    image = Image.new("RGB", (1200, 720), background)
    draw = ImageDraw.Draw(image)
    offset = sum(key.encode("utf-8")) % 180
    draw.ellipse((90 + offset, 90, 450 + offset, 450), fill=accent)
    draw.rectangle((560, 180 + offset // 3, 1080, 540 + offset // 3), outline=ink, width=18)
    draw.line((120, 610, 1080, 610), fill=ink, width=10)
    draw.text((120, 640), title[:72], fill=ink)
    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    return ContentFile(output.getvalue(), name=f"blog-seed-{key}.png")
```

- [ ] **Step 5: Verify green and commit**

```bash
uv run python manage.py test app.blog.tests.test_sample_data
git add app/blog/sample_content.py app/blog/sample_images.py app/blog/tests/test_sample_data.py
git commit -m "feat: add deterministic blog sample data"
```

Expected: all sample-data tests pass and no media is tracked.

---

### Task 5: Idempotent Population Command

**Files:**
- Create: `app/blog/management/__init__.py`
- Create: `app/blog/management/commands/__init__.py`
- Create: `app/blog/management/commands/populate_blog.py`
- Create: `app/blog/tests/test_populate_blog.py`

**Interfaces:**
- Consumes: Task 4 data/artwork and Task 1 models.
- Produces: `python manage.py populate_blog`.

- [ ] **Step 1: Write failing integration tests**

With temporary `MEDIA_ROOT`, create a default Site rooted at HomePage and call the command. Assert one index, 20 live posts, five seed images, valid 1200×720 files, and `Created 20 posts`. Run again and assert no duplicate pages/images plus `Created 0 posts` and `Updated 20 posts`. Change a seeded intro and assert rerun restores it. Add an unrelated post and assert rerun preserves it and total count becomes 21. Point the default site at the tree root and assert `CommandError` containing `root page must be a HomePage` and no blog writes.

- [ ] **Step 2: Verify red**

Run `uv run python manage.py test app.blog.tests.test_populate_blog`.

Expected: FAIL with unknown command.

- [ ] **Step 3: Implement the command**

Implement `Command.handle()` under `@transaction.atomic`. Resolve `Site.objects.get(is_default_site=True)` with explicit missing/multiple errors; require `site.root_page.specific` to be `HomePage`. Reuse or create slug `blog`, rejecting an existing sibling of another type. Publish canonical index title and slug.

Create five images titled `Blog seed: Artwork 1` through `Blog seed: Artwork 5` only when absent, using `build_seed_png()`. For each sample, find the child by stable slug, reject another page type, create or reuse `BlogPostPage`, assign every canonical field, select `images[position % 5]`, set `search_description = intro`, and call `save_revision().publish()`. Print this exact summary shape:

```python
self.stdout.write(self.style.SUCCESS(
    f"Blog ready. Index {'created' if index_created else 'updated'}. "
    f"Created {images_created} images. "
    f"Created {posts_created} posts. Updated {posts_updated} posts."
))
```

Keep helpers focused as `_get_homepage`, `_upsert_index`, `_upsert_images`, and `_upsert_posts`. Do not delete pages or images.

- [ ] **Step 4: Verify green and commit**

```bash
uv run python manage.py test app.blog.tests.test_populate_blog
uv run python manage.py test app.blog app.home
git add app/blog/management app/blog/tests/test_populate_blog.py
git commit -m "feat: add idempotent blog population command"
```

Expected: command tests and all blog/home tests pass.

---

### Task 6: Documentation and Full Verification

**Files:**
- Modify: `AGENTS.md`
- Verify: all files from Tasks 1–5

**Interfaces:**
- Produces: accurate repository guidance and fresh completion evidence.

- [ ] **Step 1: Update guidance**

Add to the structure section:

```markdown
- `app/blog/` defines the Wagtail blog index and post page types, structured article blocks, public templates, tests, deterministic sample content, and the idempotent `populate_blog` management command.
```

Add to backend commands:

```markdown
Populate or refresh the local sample blog with 20 published, fact-grounded Wagtail posts and deterministic generated artwork:

    uv run python manage.py populate_blog

The command is rerunnable, makes no network requests, and leaves unrelated editor-created posts untouched.
```

- [ ] **Step 2: Run backend verification**

```bash
uv run python manage.py test
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Expected: all tests pass, no system-check issues, and no model changes. If host MySQL is unavailable, use the documented equivalent `docker compose run --rm web ...` commands and record that choice.

- [ ] **Step 3: Run frontend and deployment integration checks**

```bash
npm test
bash scripts/test-asset-pipeline.sh
bash scripts/test-container-assets.sh
bash scripts/test-workflow-assets.sh
bash scripts/test-deployment-invariants.sh
bash scripts/test-deploy-failures.sh
```

Expected: Node tests pass and every script prints PASS.

- [ ] **Step 4: Smoke-test idempotency only against disposable development data**

```bash
uv run python manage.py migrate
uv run python manage.py populate_blog
uv run python manage.py populate_blog
```

Expected: first run creates 20 posts; second run creates 0 and updates 20. Skip this manual write against shared or production data because integration tests already isolate the behavior.

- [ ] **Step 5: Inspect scope and commit docs**

```bash
git status --short
git diff --check
git diff --stat HEAD
git add AGENTS.md
git commit -m "docs: document blog sample population"
```

Expected: no generated static/media files are staged. Commit any code correction discovered by verification separately before the docs commit.

- [ ] **Step 6: Run fresh final verification**

```bash
uv run python manage.py test
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
npm test
bash scripts/test-asset-pipeline.sh
git status --short
```

Expected: all commands exit 0, Django reports no issues and no changes, the asset pipeline prints PASS, and the working tree is clean.
