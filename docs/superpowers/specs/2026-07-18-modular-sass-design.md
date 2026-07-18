# Modular Sass Design

## Goal

Split the public site's single 433-line Sass source file into focused modules while preserving one compiled stylesheet and the existing public HTML and CSS contract. The refactor may introduce private Sass abstractions for repeated declaration sets, but it must not change templates, class names, rendered styling, asset URLs, or deployment behavior.

## Scope

The change includes:

- Replacing the contents of `assets/scss/app.scss` with an ordered module manifest.
- Separating design tokens, Sass mixins, global rules, components, page styles, and motion overrides into partials under `assets/scss/`.
- Consolidating existing repeated declaration sets behind Sass-only mixins.
- Updating `AGENTS.md` to describe the modular Sass source layout.
- Verifying that the existing asset pipeline and Django application still build and pass their checks.

The change does not include:

- Page-specific CSS bundles or additional stylesheet links.
- Template or public class-name changes.
- New CSS utility classes, design-system components, themes, or runtime dependencies.
- Visual redesign, new behavior, or JavaScript changes.
- Changes to npm commands, generated output paths, Docker, CI, or deployment workflows.

## Source layout

The Sass source will use the following layout:

```text
assets/scss/
  app.scss
  abstracts/
    _tokens.scss
    _mixins.scss
  base/
    _global.scss
    _motion.scss
  components/
    _button.scss
    _status.scss
  pages/
    _home.scss
    _blog-index.scss
    _blog-post.scss
```

`app.scss` will contain only ordered `@use` statements. The order will be abstracts, base rules, components, pages, and finally motion overrides. Abstract modules emit no CSS. Each CSS-emitting module will explicitly `@use` the tokens and mixins it consumes, so dependencies remain visible and variables do not leak into a global namespace.

The existing build remains unchanged:

```text
assets/scss/app.scss -> app/static/css/app.css
```

`app/static/css/app.css` remains the only public stylesheet and remains ignored by Git.

## Module ownership

### Abstracts

`abstracts/_tokens.scss` owns the existing colour palette and only genuinely repeated named values, including the narrow responsive breakpoint. It will not introduce a speculative spacing scale, typography scale, theme API, or configuration system.

`abstracts/_mixins.scss` owns reusable declaration sets. It emits no selectors on its own and may depend on tokens where a shared declaration requires them.

The initial mixin set is limited to patterns already repeated in the stylesheet:

- `focus-ring`
- `uppercase-label`
- `display-heading`
- `supporting-copy`
- `page-shell`
- `raised-surface`

Mixins will be preferred over Sass placeholders and `@extend`. This keeps selectors owned by their modules and avoids implicit cross-module selector grouping.

Where consumers intentionally differ, a mixin may accept narrowly scoped arguments for those existing values. A candidate will remain as local declarations if extraction reveals that it has only one real consumer or needs enough parameters to obscure the resulting CSS. The list above is therefore a boundary for permitted abstractions, not a requirement to manufacture all six regardless of fit.

### Base

`base/_global.scss` owns root typography, universal box sizing, document sizing and background, body defaults, and baseline link presentation.

`base/_motion.scss` owns the global `prefers-reduced-motion` override. It is loaded after all other CSS-emitting modules so its cascade position remains intentional.

### Components

`components/_button.scss` owns the `.button-link` component and its states.

`components/_status.scss` owns the `.status` component, its elements and changing state, and the `status-pulse` keyframes. The status component remains independent of the homepage module even though the homepage is currently its only consumer.

### Pages

`pages/_home.scss` owns the `.coming-soon` layout, panel, typography, actions, footer, and homepage-specific narrow-screen rules.

`pages/_blog-index.scss` owns the blog masthead, post grid, post cards, empty state, and their responsive rules.

`pages/_blog-post.scss` owns the article shell, header, hero, body, StreamField block presentation, and article-specific responsive rules.

Shared visual declarations used by more than one page will be included through mixins while existing selectors remain in their owning page modules.

## Compatibility requirements

The refactor must preserve:

- Every existing public selector and class name.
- The declarations and states that determine the current rendered appearance.
- The current cascade semantics, including focus and reduced-motion behavior.
- Responsive behavior at the existing narrow breakpoint.
- The single stylesheet reference in `app/templates/base.html`.
- The `npm run build`, `npm run dev`, `build:css`, and `dev:css` interfaces.
- The generated `app/static/css/app.css` output path.

Moving a responsive rule into its owning module may alter the textual order of independent rules in compiled CSS. Such reordering is acceptable only when it does not change cascade behavior. No compatibility alias or migration period is necessary because the public selectors do not change.

## Failure behavior

Sass module errors, missing namespaces, undefined tokens, or invalid mixin calls will fail the existing Sass command and therefore fail `npm run build`, the asset pipeline test, CI, image construction, or deployment in the environment where compilation runs. No additional runtime error handling is needed because Sass is used only at build time.

The compiled CSS remains generated and ignored. A failed local build must not be worked around by editing `app/static/css/app.css` directly.

## Verification

Before the refactor, compile the current Sass in expanded form to a temporary baseline outside the tracked source tree. After modularization, compile the new source and compare it with that baseline. Review any differences and confirm that every existing selector and declaration remains represented and that differences are limited to harmless ordering or grouping caused by the new module boundaries.

Run the repository's existing validation commands:

```bash
npm run build
npm test
bash scripts/test-asset-pipeline.sh
uv run python manage.py test
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

No committed CSS snapshot or new testing framework will be added for this structural refactor. The asset pipeline test already verifies that the supported entry point produces non-empty CSS at the expected output path, while the Django checks cover the application consuming that asset.

## Documentation

Update the Frontend Assets section of `AGENTS.md` to identify `assets/scss/app.scss` as the manifest and summarize the `abstracts`, `base`, `components`, and `pages` directories. The supported commands, pinned Node version, lockfile requirements, and rule against editing generated assets remain unchanged.
