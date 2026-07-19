# Homepage Blog Features Design

**Date:** 19 July 2026

## Goal

Replace the public homepage's temporary coming-soon presentation with an editorial landing page that highlights one editor-selected blog post and the three latest other blog posts.

## Scope

This change expands the existing `HomePage`; it does not introduce a general-purpose page builder or change the blog index and post page types. The homepage will contain:

- a branded masthead;
- one prominent featured blog post selected by an editor;
- a latest-posts section containing up to three distinct posts;
- a link to the full blog index.

The existing coming-soon panel, status indicator, and Wagtail footer link will be removed from the homepage.

## Editorial Model

`HomePage` will gain a nullable `featured_post` foreign key to `blog.BlogPostPage`. Wagtail will render the relationship as a page chooser restricted to that page type, and the field will use `SET_NULL` deletion behavior so deleting the selected post does not prevent the homepage from rendering.

The field is optional so existing databases can migrate safely and editors can publish the homepage before choosing a post. It will appear in the standard `HomePage` content panels.

## Content Selection

The homepage will continue to locate the first live, public `BlogIndexPage` directly beneath it. Homepage context will expose:

- `blog_page`: the live, public child blog index, when one exists;
- `featured_post`: the editor-selected post only when it belongs beneath that blog index and is live and public;
- `latest_posts`: up to three live, public posts beneath that blog index, ordered by descending post date and then descending first-published time.

The selected featured post will be excluded from `latest_posts`, even when it is among the three newest posts. This guarantees distinct homepage cards and produces four different posts whenever at least four eligible posts exist.

Restricting displayed posts to descendants of the homepage's own blog index prevents a chooser selection from another site or blog section from leaking into this homepage. Preview and normal page rendering will use the same selection rules.

## Empty and Unavailable States

The page must remain useful without assuming complete content:

- With no live blog index, post sections and the blog link are omitted.
- With no selected featured post, the featured section is omitted.
- If the selected post is unpublished, private, deleted, or outside the homepage's blog index, the featured section is omitted.
- With fewer than three eligible latest posts, only the available distinct posts are shown.
- With no eligible posts, the latest-posts section is omitted rather than displaying an error or placeholder card.

No unavailable featured post is automatically replaced by the latest post. Feature selection remains an explicit editorial decision.

## Presentation

The homepage will use the existing site's editorial visual language: display typography, uppercase labels, warm surface cards, muted metadata, accent colors, image fallbacks, and visible focus rings.

The masthead identifies the site and introduces the blog content. The featured article uses a wide, prominent layout with its image, publication date, author, title, introduction, and a clear link to the article. The latest section uses three responsive article cards derived from the existing blog-index card treatment. A link beneath or alongside the latest section leads to the full blog index.

At narrow viewport widths, the featured image and copy stack vertically and the latest grid collapses according to available width. Homepage rules remain in `assets/scss/pages/_home.scss`; generated CSS is not edited directly, and no JavaScript framework or new frontend dependency is introduced.

## Semantics and Accessibility

The template will use a single page-level heading, labelled content sections, semantic `<article>` elements, and machine-readable `<time>` values. Article titles provide the accessible name for their links. Featured and card images are decorative because the adjacent title describes the same destination, so they use empty alternative text. Decorative image links are removed from the tab order, matching the existing blog-card behavior.

All interactive links retain visible keyboard focus. Heading levels describe the masthead, featured article, and latest-post hierarchy without skipping levels.

## Testing

Model and context tests will verify:

- the optional chooser field is configured for blog posts;
- only a live, public child blog index is used;
- the featured post appears only when it is live, public, and belongs to that index;
- latest posts are ordered by post date and first-published time;
- the featured post is excluded from the latest list;
- the latest list is limited to three items;
- incomplete and unavailable content produces the documented empty states.

Rendering tests will verify the featured article, latest cards, article metadata, full-blog link, responsive-layout class hooks, and the absence of the retired coming-soon content. Tests will also cover no selection, no blog index, and an unavailable featured selection.

Verification will use the repository's configured commands:

```bash
uv run python manage.py test
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
bash scripts/test-asset-pipeline.sh
```

## Migration and Sample Content

A Django migration will add the nullable `featured_post` relationship. The deterministic `populate_blog` command does not need to assign the homepage feature: after sample posts exist, an editor can choose one through Wagtail admin. No existing post data is rewritten.

## Out of Scope

- automatic featured-post selection;
- multiple featured posts or carousel behavior;
- editable homepage marketing copy or arbitrary homepage sections;
- changes to blog post ordering on the blog index;
- changes to deterministic sample content or generated artwork;
- new JavaScript interactions or frontend dependencies.
