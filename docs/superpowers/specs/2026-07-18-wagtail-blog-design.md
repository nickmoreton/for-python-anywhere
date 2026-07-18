# Wagtail Blog Design

**Date:** 2026-07-18
**Status:** Approved design awaiting written-spec review

## Goal

Add a first-party blog application to the existing Wagtail site. The blog will live at `/blog/`, preserve the current homepage and visual identity, give editors a flexible structured article body, and include a deterministic management command that publishes 20 original sample posts grounded in verified Wagtail facts.

## Scope

The first release includes:

- a blog index page and individual blog post pages;
- publication date, simple author name, introduction, optional featured image, and structured article body;
- a newest-first card listing at `/blog/`;
- a link from the existing homepage to the blog;
- responsive public templates matching the current coming-soon page;
- a rerunnable `populate_blog` management command;
- deterministic local PNG artwork and 20 published sample posts; and
- model, rendering, command, migration, and asset verification.

The first release does not include pagination, categories, tags, RSS, comments, author profiles, related posts, or client-side interactions.

## Application Structure

Create a new `app.blog` Django application with its own models, migrations, templates, tests, and management command. Register `app.blog` in `INSTALLED_APPS`. Continue using the repository's global Sass and JavaScript entry points; do not introduce a new frontend framework or asset pipeline.

The app will contain two Wagtail page types:

### `BlogIndexPage`

`BlogIndexPage` is the landing page for the blog.

- It may be created only beneath `HomePage`.
- It accepts only `BlogPostPage` children.
- Its public context exposes live, public child posts ordered by `-date` and then `-first_published_at` for deterministic handling of equal dates.
- It renders an empty state when it has no published posts.
- The population command creates or reuses one index with slug `blog` beneath the default site's home page.

No additional editable intro field is required in this version; the index heading and concise introduction are presentation copy derived from the page title and template.

### `BlogPostPage`

`BlogPostPage` is an editor-managed article.

- It may be created only beneath `BlogIndexPage`.
- It does not accept child pages.
- `date` is a required `DateField` labelled as the post date.
- `author_name` is a required `CharField` with a maximum length of 255 characters.
- `intro` is a required concise `TextField` used on cards and at the top of the article.
- `featured_image` is an optional foreign key to Wagtail's configured image model, protected with `SET_NULL` and using the standard image chooser panel.
- `body` is a required `StreamField` with `use_json_field=True`.

The body supports these blocks:

- `heading`: a required short heading;
- `paragraph`: rich text limited to a deliberately small, accessible feature set;
- `bulleted_list`: a list of plain-text items;
- `quote`: quoted text with an optional attribution; and
- `code`: code text with an optional short language label.

The body is included in Wagtail's search index. Editor panels present metadata before body content.

## Public Presentation

The current homepage stays at `/` and retains its coming-soon copy, layout, palette, and status treatment. A visible `Read the blog` call to action links to the live `BlogIndexPage`. The link is resolved from the page tree rather than hard-coded so it remains correct if an editor changes the blog slug. If no live blog index exists, the call to action is omitted.

The blog index reuses the established visual language:

- a compact masthead with title and introduction;
- a responsive grid of semantic `<article>` cards;
- a featured-image rendition, title, intro, author, and date on each card; and
- a clear empty state when no posts are published.

Each detail page uses a restrained reading layout with a back link to the index, one page heading, article metadata, featured-image rendition, introduction, and a readable-width body. StreamField blocks receive explicit templates where needed. Code blocks preserve whitespace and scroll horizontally on narrow screens.

Featured images are treated as contextual article artwork. Templates provide suitable alt text, intrinsic rendition dimensions, and lazy loading for listing images. Decorative uses receive empty alt text. Public markup must preserve a logical heading order, visible focus states, sufficient colour contrast, and useful link text.

## Sample Data Command

The command is invoked from the repository root as:

```bash
uv run python manage.py populate_blog
```

The command performs all writes inside a database transaction where supported and reports a concise created/updated summary. It does not make network requests.

### Site and page resolution

The command resolves the default `Site`, follows its `root_page` to the specific home page, and requires that home page to be a `HomePage`. Missing, ambiguous, or structurally invalid state raises `CommandError` before content is written.

It creates or reuses the `BlogIndexPage` identified by parent and stable slug `blog`. Seeded posts are identified by that index and their stable slugs. Unrelated pages, including editor-created posts with other slugs, remain untouched.

### Idempotency

The command has a canonical in-code dataset. On every run it:

- creates missing seed images and posts;
- updates existing seeded images and posts to canonical sample values when necessary;
- publishes the canonical revision of each seeded page;
- never creates duplicates; and
- does not delete unrelated content.

After a successful run, the index contains exactly one copy of each of the 20 known seeded slugs. It may also contain unrelated posts created by editors.

### Generated artwork

Use Pillow, already present through Wagtail's image stack, to create a small deterministic set of valid PNG images in memory. Each uses the existing site's colour family, simple geometric motifs, fixed dimensions, and no external logos or third-party assets. Images are saved through Wagtail's configured image model and storage backend, with stable titles and filenames so they can be reused on later runs.

The generated source images are runtime media and are not committed to Git. Tests use temporary media storage.

### Sample writing

The command embeds original, synthetic copy written specifically for this project. It does not quote, scrape, download, or closely mirror Wagtail articles. Fictional author names make clear that the posts are sample editorial content rather than official Wagtail publications.

The 20 topics are:

1. Understanding Wagtail's page tree
2. Building flexible articles with StreamField
3. Choosing useful StreamField block boundaries
4. Working with Wagtail image renditions
5. Writing context-aware image alternative text
6. Previewing content before publication
7. Revisions, drafts, and publishing
8. Organising reusable content with snippets
9. Searching Wagtail content
10. Managing redirects after URL changes
11. Editorial workflows and moderation
12. Supporting multiple sites
13. Localising content with Wagtail
14. Using Wagtail as a headless CMS
15. Improving page performance with caching
16. Prefetching image renditions efficiently
17. Testing page types with `WagtailPageTestCase`
18. Designing accessible editor-controlled content
19. Extending the Wagtail admin with hooks
20. What Wagtail 7.4 LTS means for a project

Facts used in the dataset will be checked against first-party sources at implementation time. The command's module docstring or adjacent source comment records the source URLs and the date they were checked. Sources are research provenance only and are not appended to the fictional public articles.

## Data Flow

For editor-created content, Wagtail's page editor validates the model fields and StreamField structure, saves revisions, and publishes pages through the standard page lifecycle. Public requests route through Wagtail's existing catch-all URLs. The index context queries only live, public descendants, and templates request appropriately sized Wagtail image renditions.

For sample data, the command resolves the site and parent pages, generates or reuses media, constructs canonical StreamField values, creates or updates page revisions, and publishes them. A second invocation converges on the same state.

## Error Handling

- Invalid default-site or home-page structure raises a specific `CommandError` with recovery guidance.
- Image generation or storage errors fail the command rather than leaving apparently successful partial seed data.
- Invalid canonical StreamField data is detected during command tests and page validation.
- The public index handles zero published posts without error.
- Missing featured images use an intentional styled fallback rather than a broken image element.
- A deleted Wagtail image sets `featured_image` to null and leaves the article renderable.

## Testing

Use Django's test framework and Wagtail's `WagtailPageTestCase` utilities.

### Model and page-tree tests

- `BlogIndexPage` is allowed only beneath `HomePage`.
- `BlogPostPage` is allowed only beneath `BlogIndexPage` and rejects children.
- Required fields and supported StreamField blocks are represented correctly.
- The index exposes only live public posts in deterministic newest-first order.

### Rendering tests

- The index and detail pages are routable and use their intended templates.
- The index renders the empty state and populated card state.
- Cards and articles render title, date, author, intro, and optional image correctly.
- Body blocks render semantic headings, paragraphs, lists, quotes, and code.
- The homepage links to a live blog and omits the action when none exists.

### Management-command tests

- The first run creates one index, 20 published posts, and the expected reusable images.
- The second run creates no duplicate pages or images.
- Canonical seeded content is restored on rerun when a seeded page has changed.
- Unrelated editor-created posts remain unchanged.
- Generated files are valid images accepted by Wagtail.
- Missing or invalid default-site/home-page state raises `CommandError`.
- Representative seeded posts contain expected structured, fact-grounded content.

### Project verification

Run the repository's documented checks:

```bash
uv run python manage.py test
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
bash scripts/test-asset-pipeline.sh
```

If the host MySQL service is unavailable, run the equivalent Django checks using the documented Docker Compose workflow. Review the generated blog migration before applying it.

## Documentation Impact

Update `AGENTS.md` during implementation because the project structure will gain `app/blog/` and a new supported management command. No other operational or deployment workflow changes are expected.

## Fact-Checking Sources

The sample dataset will be checked primarily against these first-party resources:

- [Wagtail 7.4 documentation](https://docs.wagtail.org/en/stable/)
- [StreamField documentation](https://docs.wagtail.org/en/stable/topics/streamfield.html)
- [Performance documentation](https://docs.wagtail.org/en/stable/advanced_topics/performance.html)
- [Image documentation](https://docs.wagtail.org/en/stable/advanced_topics/images/index.html)
- [Internationalization documentation](https://docs.wagtail.org/en/stable/advanced_topics/i18n.html)
- [Headless support documentation](https://docs.wagtail.org/en/stable/advanced_topics/headless.html)
- [Testing documentation](https://docs.wagtail.org/en/stable/advanced_topics/testing.html)
- [Wagtail 7.4 LTS release notes](https://docs.wagtail.org/en/stable-7.4.x/releases/7.4.html)
- [Wagtail feature overview](https://wagtail.org/features/)

## Acceptance Criteria

The design is complete when an editor can create and publish structured blog posts beneath `/blog/`, visitors can navigate from the retained homepage to a responsive blog index and readable article pages, and one rerunnable command produces 20 published, original, fact-grounded sample posts with deterministic local artwork without accessing the network or duplicating content.
