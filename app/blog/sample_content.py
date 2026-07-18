"""Original sample writing fact-checked against first-party Wagtail sources.

Checked 2026-07-18:
https://docs.wagtail.org/en/stable/topics/streamfield.html
https://docs.wagtail.org/en/stable/advanced_topics/performance.html
https://docs.wagtail.org/en/stable/advanced_topics/images/index.html
https://docs.wagtail.org/en/stable/advanced_topics/i18n.html
https://docs.wagtail.org/en/stable/advanced_topics/headless.html
https://docs.wagtail.org/en/stable/advanced_topics/testing.html
https://docs.wagtail.org/en/stable-7.4.x/releases/7.4.html
https://wagtail.org/features/
"""

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
        blocks = [
            ("heading", "Why it matters"),
            ("paragraph", f"<p>{self.facts[0]}</p>"),
            ("heading", "What to keep in mind"),
            ("bulleted_list", list(self.facts[1:])),
            (
                "quote",
                {
                    "text": self.takeaway,
                    "attribution": self.author_name,
                },
            ),
        ]
        if self.code:
            blocks.append(
                (
                    "code",
                    {
                        "language": self.code_language,
                        "code": self.code,
                    },
                )
            )
        return blocks


SAMPLE_POSTS = (
    SamplePost(
        "Understanding Wagtail's page tree",
        "understanding-wagtails-page-tree",
        "A practical map of how Wagtail turns an editorial hierarchy into routes and relationships.",
        (
            "Wagtail pages form a tree, so each page has a parent, a path, and an editorial position.",
            "A page's slug and ancestors contribute to its default URL.",
            "Parent and child type rules keep editors inside the intended information architecture.",
        ),
        "Treat the page tree as part of the content model, not merely an admin menu.",
        AUTHORS[0],
        0,
        "python",
        'parent_page_types = ["home.HomePage"]',
    ),
    SamplePost(
        "Building flexible articles with StreamField",
        "building-flexible-articles-with-streamfield",
        "Use ordered blocks to give editors freedom without giving up structure.",
        (
            "StreamField stores an ordered sequence of typed blocks and suits articles with mixed content.",
            "Editors can repeat and rearrange the block choices a project exposes.",
            "The field preserves structured JSON rather than reducing the article to presentation-shaped HTML.",
        ),
        "A small block vocabulary usually serves editors better than an unlimited toolbox.",
        AUTHORS[1],
        3,
        "python",
        'body = StreamField([("paragraph", blocks.RichTextBlock())])',
    ),
    SamplePost(
        "Choosing useful StreamField block boundaries",
        "choosing-useful-streamfield-block-boundaries",
        "Model meaning first so templates remain stable as presentation evolves.",
        (
            "A StreamField block works best when it represents a recognizable editorial unit.",
            "StructBlock groups related values, while ListBlock represents a repeatable sequence.",
            "Custom block validation can enforce relationships that individual fields cannot express.",
        ),
        "Good boundaries make content understandable without inspecting its HTML.",
        AUTHORS[2],
        6,
    ),
    SamplePost(
        "Working with Wagtail image renditions",
        "working-with-wagtail-image-renditions",
        "Deliver appropriately sized images while retaining one editorial source asset.",
        (
            "Wagtail creates renditions from an original image according to a filter specification.",
            "The image template tag supplies the generated rendition's dimensions to the output.",
            "Existing renditions are reused instead of being recreated for every request.",
        ),
        "Ask templates for the image they need instead of serving the original everywhere.",
        AUTHORS[3],
        9,
        "django",
        "{% image page.featured_image fill-720x432 %}",
    ),
    SamplePost(
        "Writing context-aware image alternative text",
        "writing-context-aware-image-alternative-text",
        "Alternative text works best when it reflects why an image appears in a specific place.",
        (
            "Accessible image text depends on context, so one source image can need different treatment in different uses.",
            "Decorative images should not repeat information that nearby text already provides.",
            "Wagtail's ImageBlock supports contextual alternative text for images placed in StreamField.",
        ),
        "Describe the image's purpose in the page, not every visible detail.",
        AUTHORS[0],
        12,
    ),
    SamplePost(
        "Previewing content before publication",
        "previewing-content-before-publication",
        "Use Wagtail preview to inspect editorial changes before they become public.",
        (
            "Wagtail page previews render draft content without first publishing it.",
            "Projects can define multiple preview modes when content has more than one presentation.",
            "Preview participates in the editor workflow while a page is still being revised.",
        ),
        "Preview is a publishing safety net, not a replacement for accessible templates and tests.",
        AUTHORS[1],
        15,
    ),
    SamplePost(
        "Revisions, drafts, and publishing",
        "revisions-drafts-and-publishing",
        "Separate saving editorial work from making that work public.",
        (
            "Wagtail stores page revisions so editors can save drafts and revisit earlier states.",
            "Publishing selects a revision to become the live representation of a page.",
            "Unpublishing removes a page from public delivery without deleting its editorial record.",
        ),
        "A deliberate publishing lifecycle helps teams change content with confidence.",
        AUTHORS[2],
        18,
    ),
    SamplePost(
        "Organising reusable content with snippets",
        "organising-reusable-content-with-snippets",
        "Use snippets for structured content that belongs in more than one page context.",
        (
            "Wagtail snippets are Django models registered for editing in the Wagtail admin.",
            "Snippet viewsets can shape listing, search, and editor behavior.",
            "A reusable concept avoids duplicated facts when several pages depend on it.",
        ),
        "Reuse content because it has shared meaning, not only because two pages look alike.",
        AUTHORS[3],
        21,
    ),
    SamplePost(
        "Searching Wagtail content",
        "searching-wagtail-content",
        "Make the fields that matter discoverable through Wagtail's search index.",
        (
            "Page titles are searchable by default, and custom fields can be added with SearchField.",
            "Wagtail can use its database search backend without an external search service.",
            "Projects with larger relevance or scale needs can choose a dedicated backend.",
        ),
        "Index intentional editorial fields and keep search proportional to the site.",
        AUTHORS[0],
        24,
        "python",
        'search_fields = Page.search_fields + [index.SearchField("intro")]',
    ),
    SamplePost(
        "Managing redirects after URL changes",
        "managing-redirects-after-url-changes",
        "Preserve useful journeys when editors move pages or change their slugs.",
        (
            "Wagtail's redirects application can send an old path to a new destination.",
            "Redirect middleware must be installed for redirect records to take effect.",
            "Site-aware redirect records keep multi-site installations from crossing boundaries unexpectedly.",
        ),
        "A changed URL should include a planned route for existing visitors.",
        AUTHORS[1],
        27,
    ),
    SamplePost(
        "Editorial workflows and moderation",
        "editorial-workflows-and-moderation",
        "Add review stages when publishing responsibility is shared across a team.",
        (
            "Wagtail workflows can require pages to pass moderation tasks before publication.",
            "Tasks can be assigned to groups so responsibility follows editorial roles.",
            "Small teams can retain direct publishing instead of adopting unnecessary workflow complexity.",
        ),
        "Use the lightest publishing process that still makes ownership clear.",
        AUTHORS[2],
        30,
    ),
    SamplePost(
        "Supporting multiple sites",
        "supporting-multiple-sites",
        "One Wagtail project can serve distinct domains from different page-tree roots.",
        (
            "Wagtail Site records connect hostnames and ports to root pages.",
            "Page URL resolution uses site context to choose the correct public route.",
            "Shared code does not require every site to share the same content hierarchy or brand.",
        ),
        "Model each site's boundary explicitly and pass request context when resolving many URLs.",
        AUTHORS[3],
        33,
    ),
    SamplePost(
        "Localising content with Wagtail",
        "localising-content-with-wagtail",
        "Understand how locales and translation relationships shape multilingual content.",
        (
            "Wagtail stores localized content in a separate page tree for each locale.",
            "Translated pages share a translation key while keeping locale-specific records.",
            "Wagtail supplies translation infrastructure, with simple translation and Wagtail Localize providing editorial approaches.",
        ),
        "Plan URL routing and editorial ownership alongside the language list.",
        AUTHORS[0],
        36,
    ),
    SamplePost(
        "Using Wagtail as a headless CMS",
        "using-wagtail-as-a-headless-cms",
        "Keep Wagtail's editing strengths while delivering content to a separate frontend.",
        (
            "Wagtail includes a native read-only REST API for exposing page data.",
            "GraphQL integrations rely on third-party packages rather than native Wagtail support.",
            "Headless preview, routing, rich text, and multi-site behavior require explicit architectural choices.",
        ),
        "Choose headless delivery for a concrete frontend need, not simply because it is fashionable.",
        AUTHORS[1],
        39,
    ),
    SamplePost(
        "Improving page performance with caching",
        "improving-page-performance-with-caching",
        "Cache carefully without leaking previews or serving stale editorial content.",
        (
            "Wagtail can integrate with frontend caches and purge them when pages change.",
            "Wagtail-specific template cache tags avoid exposing preview content through an ordinary fragment cache.",
            "Passing request or current-site context into URL resolution can reduce repeated lookup work.",
        ),
        "Measure first, then cache the work that actually matters.",
        AUTHORS[2],
        42,
    ),
    SamplePost(
        "Prefetching image renditions efficiently",
        "prefetching-image-renditions-efficiently",
        "Avoid repeated rendition lookups when a listing needs predictable image sizes.",
        (
            "Wagtail image querysets can prefetch selected renditions.",
            "Prefetching is useful for listings that render many images with known filters.",
            "A dynamic image URL can defer rendition work when only a URL is needed.",
        ),
        "Match rendition strategy to the query and template rather than optimizing blindly.",
        AUTHORS[3],
        45,
    ),
    SamplePost(
        "Testing page types with WagtailPageTestCase",
        "testing-page-types-with-wagtailpagetestcase",
        "Protect routing and page-tree rules with Wagtail's focused test assertions.",
        (
            "WagtailPageTestCase extends Django's TestCase with page-specific assertions.",
            "It can verify routability, renderability, and allowed parent and child types.",
            "Small setup helpers keep page-tree construction readable across rendering tests.",
        ),
        "A page model is not finished until its editorial constraints and public route are tested.",
        AUTHORS[0],
        48,
        "python",
        "self.assertPageIsRenderable(page)",
    ),
    SamplePost(
        "Designing accessible editor-controlled content",
        "designing-accessible-editor-controlled-content",
        "Content models and templates share responsibility for accessible public pages.",
        (
            "Accessible CMS output depends on content modeling, frontend markup, and author guidance.",
            "A constrained heading block can protect document hierarchy better than unrestricted rich text.",
            "Wagtail offers editor accessibility checks, while project templates still determine public semantics.",
        ),
        "Build safe defaults into the model so accessibility is not left to memory.",
        AUTHORS[1],
        51,
    ),
    SamplePost(
        "Extending the Wagtail admin with hooks",
        "extending-the-wagtail-admin-with-hooks",
        "Add project-specific admin behavior through documented extension points.",
        (
            "Wagtail discovers wagtail_hooks.py modules in installed Django applications.",
            "Hooks can register admin URLs, menu items, reports, and other extensions.",
            "Focused hook functions can delegate substantial work to modules that are easier to test.",
        ),
        "Keep admin extensions small at the boundary and explicit about permissions.",
        AUTHORS[2],
        54,
        "python",
        '@hooks.register("register_admin_urls")\ndef register_admin_urls():\n    return []',
    ),
    SamplePost(
        "What Wagtail 7.4 LTS means for a project",
        "what-wagtail-74-lts-means-for-a-project",
        "Use the long-term support release as a stable base while reviewing upgrade notes carefully.",
        (
            "Wagtail 7.4 is designated as a long-term support release.",
            "Its release notes include autosave and concurrent-editing experience improvements.",
            "LTS status does not remove the need to test project customizations and follow maintenance releases.",
        ),
        "A stable release line is most useful when the project keeps its own tests current.",
        AUTHORS[3],
        57,
    ),
)
