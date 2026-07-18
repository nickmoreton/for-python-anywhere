# Modular Sass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the public site's monolithic Sass source into focused, explicitly namespaced modules while preserving one compiled stylesheet and the existing rendered design.

**Architecture:** `assets/scss/app.scss` becomes an ordered `@use` manifest. Private abstract modules provide tokens and declaration-only mixins; base, component, and page modules own all emitted selectors, with the reduced-motion override loaded last.

**Tech Stack:** Dart Sass 1.101.0, npm scripts, Bash integration checks, Django/Wagtail tests

## Global Constraints

- Keep one stylesheet build from `assets/scss/app.scss` to ignored output `app/static/css/app.css`.
- Do not change templates, public selectors, class names, rendered styling, asset URLs, JavaScript, npm commands, Docker, CI, or deployment workflows.
- Use Sass `@use` with explicit namespaces; do not use deprecated `@import`, global variable leakage, public utility classes, placeholders, or `@extend`.
- Restrict tokens to the existing colour palette and the existing `34rem` narrow breakpoint.
- Extract only repeated declaration sets that remain clear with few or no arguments; keep a candidate local if abstraction obscures its CSS.
- Preserve focus, responsive, animation, and reduced-motion behavior.
- Do not edit or commit generated `app/static/css/app.css` or `app/static/js/app.js`.

---

## File Structure

**Create:**

- `assets/scss/abstracts/_tokens.scss` — colour and breakpoint values; emits no CSS.
- `assets/scss/abstracts/_mixins.scss` — private declaration mixins; emits no CSS.
- `assets/scss/base/_global.scss` — document-level and element defaults.
- `assets/scss/base/_motion.scss` — final global reduced-motion override.
- `assets/scss/components/_button.scss` — `.button-link` and its states.
- `assets/scss/components/_status.scss` — status indicator and pulse keyframes.
- `assets/scss/pages/_home.scss` — coming-soon homepage presentation.
- `assets/scss/pages/_blog-index.scss` — blog masthead, grid, cards, and empty state.
- `assets/scss/pages/_blog-post.scss` — article layout and StreamField block presentation.

**Modify:**

- `assets/scss/app.scss` — ordered manifest only.
- `scripts/test-asset-pipeline.sh` — assert the supported modular source contract.
- `AGENTS.md` — document the modular Sass layout.

**Unchanged consumers:**

- `package.json` continues to compile the same entry point to the same output.
- `app/templates/base.html` continues to load only `css/app.css`.

---

### Task 1: Establish and implement the modular Sass contract

**Files:**

- Create: `assets/scss/abstracts/_tokens.scss`
- Create: `assets/scss/abstracts/_mixins.scss`
- Create: `assets/scss/base/_global.scss`
- Create: `assets/scss/base/_motion.scss`
- Create: `assets/scss/components/_button.scss`
- Create: `assets/scss/components/_status.scss`
- Create: `assets/scss/pages/_home.scss`
- Create: `assets/scss/pages/_blog-index.scss`
- Create: `assets/scss/pages/_blog-post.scss`
- Modify: `assets/scss/app.scss`
- Modify: `scripts/test-asset-pipeline.sh:12-17`
- Test: `scripts/test-asset-pipeline.sh`

**Interfaces:**

- Consumes: `package.json`'s existing Sass entry point and the selectors currently defined by `assets/scss/app.scss`.
- Produces: namespaced token variables `$ink`, `$muted`, `$line`, `$surface`, `$canvas`, `$accent`, `$accent-soft`, and `$narrow-breakpoint`; mixins `focus-ring`, `uppercase-label($letter-spacing: 0.1em, $font-size: 0.8rem)`, `display-heading`, `supporting-copy`, and `page-shell`; the unchanged public CSS selector contract.

- [ ] **Step 1: Capture the pre-refactor expanded CSS baseline**

Run:

```bash
baseline_css="$(git rev-parse --git-path modular-sass-baseline.css)"
npx sass --no-source-map --style=expanded assets/scss/app.scss "$baseline_css"
test -s "$baseline_css"
```

Expected: exit 0 and a non-empty untracked baseline inside Git's private directory, not the worktree.

- [ ] **Step 2: Add a failing source-layout contract to the asset pipeline test**

Insert the following immediately after the existing `assets/scss/app.scss` assertion in `scripts/test-asset-pipeline.sh`:

```bash
expected_sass_modules=(
    assets/scss/abstracts/_tokens.scss
    assets/scss/abstracts/_mixins.scss
    assets/scss/base/_global.scss
    assets/scss/base/_motion.scss
    assets/scss/components/_button.scss
    assets/scss/components/_status.scss
    assets/scss/pages/_home.scss
    assets/scss/pages/_blog-index.scss
    assets/scss/pages/_blog-post.scss
)

for module in "${expected_sass_modules[@]}"; do
    [[ -f "$module" ]] || fail "Sass module is missing: $module"
done

expected_sass_uses=(
    '@use "abstracts/tokens";'
    '@use "abstracts/mixins";'
    '@use "base/global";'
    '@use "components/button";'
    '@use "components/status";'
    '@use "pages/home";'
    '@use "pages/blog-index";'
    '@use "pages/blog-post";'
    '@use "base/motion";'
)

for use_statement in "${expected_sass_uses[@]}"; do
    grep -Fxq "$use_statement" assets/scss/app.scss \
        || fail "Sass manifest is missing: $use_statement"
done

[[ $(rg -c '^@use ' assets/scss/app.scss) -eq ${#expected_sass_uses[@]} ]] \
    || fail "Sass manifest contains unexpected imports"
if rg -q '[{}]' assets/scss/app.scss; then
    fail "Sass manifest must not emit styles directly"
fi
```

- [ ] **Step 3: Run the contract and verify that it fails for the absent modules**

Run:

```bash
bash scripts/test-asset-pipeline.sh
```

Expected: exit 1 with `FAIL: Sass module is missing: assets/scss/abstracts/_tokens.scss`.

- [ ] **Step 4: Create the token module**

Create `assets/scss/abstracts/_tokens.scss` with:

```scss
$ink: #202321;
$muted: #666d68;
$line: #dfe4e0;
$surface: #ffffff;
$canvas: #f2f4f1;
$accent: #356b52;
$accent-soft: #dce9e1;
$narrow-breakpoint: 34rem;
```

- [ ] **Step 5: Create the private mixin module**

Create `assets/scss/abstracts/_mixins.scss` with:

```scss
@use "tokens";

@mixin focus-ring {
  outline: 0.2rem solid tokens.$accent;
  outline-offset: 0.22rem;
}

@mixin uppercase-label($letter-spacing: 0.1em, $font-size: 0.8rem) {
  font-size: $font-size;
  font-weight: 700;
  letter-spacing: $letter-spacing;
  text-transform: uppercase;
}

@mixin display-heading {
  font-weight: 600;
  letter-spacing: -0.055em;
  line-height: 0.98;
}

@mixin supporting-copy {
  color: tokens.$muted;
}

@mixin page-shell {
  width: min(100% - 2.5rem, 76rem);
  margin-inline: auto;
  padding-block: clamp(2rem, 6vw, 5rem);
}
```

Do not add `raised-surface`: the panel and card declaration sets need enough differing arguments that the abstraction would hide rather than clarify their CSS.

- [ ] **Step 6: Create the base modules**

Create `assets/scss/base/_global.scss` with:

```scss
@use "../abstracts/tokens";

:root {
  color-scheme: light;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
  font-synthesis: none;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

html {
  min-width: 20rem;
  background: tokens.$canvas;
}

body {
  min-height: 100vh;
  margin: 0;
  color: tokens.$ink;
  background:
    radial-gradient(
      circle at 20% 10%,
      rgba(tokens.$accent, 0.08),
      transparent 32rem
    ),
    tokens.$canvas;
  line-height: 1.6;
}

a {
  color: inherit;
  text-underline-offset: 0.18em;
}

a:hover {
  color: tokens.$accent;
}
```

Create `assets/scss/base/_motion.scss` with:

```scss
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
  }
}
```

- [ ] **Step 7: Create the component modules**

Create `assets/scss/components/_button.scss` with:

```scss
@use "../abstracts/mixins";
@use "../abstracts/tokens";

.button-link {
  display: inline-flex;
  align-items: center;
  min-height: 2.75rem;
  padding: 0.65rem 1rem;
  border-radius: 999px;
  color: tokens.$surface;
  background: tokens.$accent;
  font-size: 0.9rem;
  font-weight: 700;
  text-decoration: none;
}

.button-link:hover {
  color: tokens.$surface;
  background: #2b5944;
}

.button-link:focus-visible {
  @include mixins.focus-ring;
}
```

Create `assets/scss/components/_status.scss` with:

```scss
@use "../abstracts/tokens";

.status {
  display: inline-flex;
  align-items: center;
  gap: 0.7rem;
  min-height: 2.5rem;
  padding: 0.55rem 0.9rem;
  border: 1px solid tokens.$accent-soft;
  border-radius: 999px;
  color: tokens.$accent;
  background: rgba(tokens.$accent-soft, 0.45);
  font-size: 0.85rem;
  font-weight: 650;
}

.status__dot {
  width: 0.55rem;
  height: 0.55rem;
  flex: 0 0 auto;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 0 0 rgba(tokens.$accent, 0.35);
  animation: status-pulse 2.4s ease-out infinite;
}

.status__message {
  transition: opacity 180ms ease, transform 180ms ease;
}

.status__message.is-changing {
  opacity: 0;
  transform: translateY(0.2rem);
}

@keyframes status-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(tokens.$accent, 0.35);
  }

  70%,
  100% {
    box-shadow: 0 0 0 0.6rem rgba(tokens.$accent, 0);
  }
}
```

- [ ] **Step 8: Create the homepage module**

Create `assets/scss/pages/_home.scss` with:

```scss
@use "../abstracts/mixins";
@use "../abstracts/tokens";

.coming-soon {
  display: grid;
  min-height: 100vh;
  grid-template-rows: 1fr auto;
  gap: 2rem;
  padding: clamp(1.25rem, 5vw, 4rem);
}

.coming-soon__panel {
  width: min(100%, 44rem);
  margin: auto;
  padding: clamp(2rem, 7vw, 5rem);
  border: 1px solid rgba(tokens.$line, 0.9);
  border-radius: 1.5rem;
  background: rgba(tokens.$surface, 0.92);
  box-shadow: 0 1.5rem 4rem rgba(tokens.$ink, 0.08);
}

.coming-soon__brand,
.coming-soon__eyebrow,
.coming-soon__intro,
.coming-soon h1 {
  margin-top: 0;
}

.coming-soon__brand {
  @include mixins.uppercase-label(0.12em, 0.85rem);

  margin-bottom: clamp(3rem, 9vw, 6rem);
}

.coming-soon__eyebrow {
  @include mixins.uppercase-label(0.14em);

  margin-bottom: 0.75rem;
  color: tokens.$accent;
}

.coming-soon h1 {
  @include mixins.display-heading;

  max-width: 12ch;
  margin-bottom: 1.25rem;
  font-size: clamp(2.5rem, 8vw, 5.5rem);
}

.coming-soon__intro {
  @include mixins.supporting-copy;

  max-width: 35rem;
  margin-bottom: 2rem;
  font-size: clamp(1rem, 2vw, 1.15rem);
}

.coming-soon__footer {
  color: tokens.$muted;
  font-size: 0.8rem;
  text-align: center;
}

.coming-soon__actions {
  margin: 0 0 1.5rem;
}

@media (max-width: tokens.$narrow-breakpoint) {
  .coming-soon__panel {
    border-radius: 1rem;
  }

  .coming-soon__brand {
    margin-bottom: 3rem;
  }
}
```

- [ ] **Step 9: Create the blog index module**

Create `assets/scss/pages/_blog-index.scss` with:

```scss
@use "../abstracts/mixins";
@use "../abstracts/tokens";

.blog-shell {
  @include mixins.page-shell;
}

.blog-masthead {
  max-width: 52rem;
  margin-bottom: clamp(2.5rem, 6vw, 5rem);
}

.blog-masthead a:focus-visible,
.blog-card a:focus-visible {
  @include mixins.focus-ring;
}

.blog-masthead__brand,
.blog-masthead__eyebrow,
.blog-empty__eyebrow {
  @include mixins.uppercase-label;
}

.blog-masthead__brand {
  display: inline-block;
  margin-bottom: clamp(2rem, 6vw, 4rem);
}

.blog-masthead__eyebrow,
.blog-empty__eyebrow {
  margin-bottom: 0.75rem;
  color: tokens.$accent;
}

.blog-masthead h1 {
  @include mixins.display-heading;

  max-width: 14ch;
  margin: 0 0 1.25rem;
  font-size: clamp(2.7rem, 8vw, 5.8rem);
}

.blog-masthead__intro {
  @include mixins.supporting-copy;

  max-width: 42rem;
  margin: 0;
  font-size: clamp(1.05rem, 2vw, 1.3rem);
}

.blog-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 19rem), 1fr));
  gap: 1.5rem;
}

.blog-card,
.blog-empty {
  overflow: hidden;
  border: 1px solid rgba(tokens.$line, 0.95);
  border-radius: 1.25rem;
  background: rgba(tokens.$surface, 0.94);
  box-shadow: 0 1rem 3rem rgba(tokens.$ink, 0.06);
}

.blog-card__image-link {
  display: block;
  background: tokens.$accent-soft;
}

.blog-card__image {
  display: block;
  width: 100%;
  aspect-ratio: 5 / 3;
  object-fit: cover;
}

.blog-card__image--fallback {
  background:
    radial-gradient(
      circle at 25% 30%,
      rgba(tokens.$surface, 0.8) 0 8%,
      transparent 9%
    ),
    linear-gradient(135deg, tokens.$accent-soft, rgba(tokens.$accent, 0.72));
}

.blog-card__body {
  padding: 1.5rem;
}

.blog-card__meta {
  margin: 0 0 0.7rem;
  color: tokens.$muted;
  font-size: 0.78rem;
}

.blog-card h2 {
  margin: 0 0 0.75rem;
  font-size: clamp(1.35rem, 3vw, 1.8rem);
  line-height: 1.15;
}

.blog-card h2 a {
  text-decoration: none;
}

.blog-card__body > p:last-child,
.blog-empty > p:last-child {
  margin-bottom: 0;
  color: tokens.$muted;
}

.blog-empty {
  padding: clamp(2rem, 6vw, 4rem);
}

.blog-empty h2 {
  margin: 0 0 0.75rem;
  font-size: clamp(2rem, 5vw, 3.4rem);
  line-height: 1.05;
}

@media (max-width: tokens.$narrow-breakpoint) {
  .blog-shell {
    width: min(100% - 1.5rem, 76rem);
  }

  .blog-card,
  .blog-empty {
    border-radius: 1rem;
  }
}
```

- [ ] **Step 10: Create the blog post module**

Create `assets/scss/pages/_blog-post.scss` with:

```scss
@use "../abstracts/mixins";
@use "../abstracts/tokens";

.article-shell {
  @include mixins.page-shell;
}

.article {
  width: min(100%, 62rem);
  margin-inline: auto;
}

.article__header {
  max-width: 52rem;
  margin-bottom: clamp(2.5rem, 6vw, 5rem);
}

.article a:focus-visible {
  @include mixins.focus-ring;
}

.article__back {
  display: inline-block;
  margin-bottom: clamp(2rem, 6vw, 4rem);
}

.article__meta {
  @include mixins.uppercase-label;

  margin-bottom: 0.75rem;
  color: tokens.$accent;
}

.article h1 {
  @include mixins.display-heading;

  max-width: 14ch;
  margin: 0 0 1.25rem;
  font-size: clamp(2.7rem, 8vw, 5.8rem);
}

.article__intro {
  @include mixins.supporting-copy;

  max-width: 42rem;
  margin: 0;
  font-size: clamp(1.05rem, 2vw, 1.3rem);
}

.article__hero {
  margin: 0 0 clamp(2.5rem, 6vw, 5rem);
}

.article__hero img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 1.25rem;
}

.article__body {
  width: min(100%, 44rem);
  margin-inline: auto;
  font-size: 1.05rem;
}

.article-block {
  margin-block: 0 1.5rem;
}

.article-block--heading {
  margin-top: 2.7rem;
  font-size: clamp(1.6rem, 4vw, 2.3rem);
  line-height: 1.15;
}

.article-block--paragraph > :first-child,
.article-block--paragraph > :last-child {
  margin-block: 0;
}

.article-block--list {
  padding-left: 1.4rem;
}

.article-block--list li + li {
  margin-top: 0.45rem;
}

.article-block--quote {
  margin-inline: 0;
  padding: 1.5rem;
  border-left: 0.3rem solid tokens.$accent;
  border-radius: 0 1rem 1rem 0;
  background: rgba(tokens.$accent-soft, 0.55);
}

.article-block--quote p {
  margin-top: 0;
  font-size: 1.2rem;
}

.article-block--quote footer {
  color: tokens.$muted;
  font-size: 0.85rem;
}

.article-block--code {
  overflow: hidden;
  border-radius: 1rem;
  color: #eef5f0;
  background: tokens.$ink;
}

.article-block__language {
  margin: 0;
  padding: 0.65rem 1rem;
  border-bottom: 1px solid rgba(tokens.$surface, 0.16);
  color: rgba(tokens.$surface, 0.75);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.article-block--code pre {
  overflow-x: auto;
  margin: 0;
  padding: 1.25rem;
}

.article-block--code code {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 0.9rem;
}

@media (max-width: tokens.$narrow-breakpoint) {
  .article-shell {
    width: min(100% - 1.5rem, 76rem);
  }

  .article__hero img {
    border-radius: 1rem;
  }
}
```

- [ ] **Step 11: Replace the monolith with the ordered manifest**

Replace `assets/scss/app.scss` with:

```scss
@use "abstracts/tokens";
@use "abstracts/mixins";
@use "base/global";
@use "components/button";
@use "components/status";
@use "pages/home";
@use "pages/blog-index";
@use "pages/blog-post";
@use "base/motion";
```

- [ ] **Step 12: Compile and inspect the CSS delta against the baseline**

Run:

```bash
baseline_css="$(git rev-parse --git-path modular-sass-baseline.css)"
candidate_css="$(git rev-parse --git-path modular-sass-candidate.css)"
npx sass --no-source-map --style=expanded assets/scss/app.scss "$candidate_css"
git diff --no-index --word-diff=plain "$baseline_css" "$candidate_css" || true
```

Expected: the candidate compiles. Review the complete diff. Every old selector and declaration must remain; acceptable differences are splitting formerly grouped cross-page selectors, moving component keyframes beside the component, and relocating page-specific narrow-screen rules beside their page. Correct any missing or changed declaration before continuing.

- [ ] **Step 13: Run the focused frontend checks**

Run:

```bash
npm run build
npm test
bash scripts/test-asset-pipeline.sh
```

Expected: the build completes, all 3 JavaScript tests pass, and the script prints `PASS: asset pipeline`.

- [ ] **Step 14: Remove private comparison artifacts and commit the Sass refactor**

Run:

```bash
baseline_css="$(git rev-parse --git-path modular-sass-baseline.css)"
candidate_css="$(git rev-parse --git-path modular-sass-candidate.css)"
rm -f "$baseline_css" "$candidate_css"
git add assets/scss scripts/test-asset-pipeline.sh
git commit -m "refactor: split Sass into focused modules"
```

Expected: a commit containing only the Sass modules, manifest, and asset-pipeline contract test. Generated CSS and JavaScript remain unstaged.

---

### Task 2: Document the layout and run full validation

**Files:**

- Modify: `scripts/test-asset-pipeline.sh:80-85` after Task 1 insertions
- Modify: `AGENTS.md:19-35`
- Test: `scripts/test-asset-pipeline.sh`

**Interfaces:**

- Consumes: Task 1's manifest and `abstracts`, `base`, `components`, and `pages` directories.
- Produces: repository guidance that identifies `app.scss` as the manifest and describes each module directory without changing supported commands.

- [ ] **Step 1: Add failing documentation assertions**

Insert these assertions with the existing `AGENTS.md` assertions near the end of `scripts/test-asset-pipeline.sh`:

```bash
rg -q '`assets/scss/app\.scss` is the Sass manifest' AGENTS.md \
    || fail "AGENTS.md does not document the Sass manifest"
rg -q '`abstracts/`, `base/`, `components/`, and `pages/`' AGENTS.md \
    || fail "AGENTS.md does not document the Sass module directories"
```

- [ ] **Step 2: Run the documentation contract and verify that it fails**

Run:

```bash
bash scripts/test-asset-pipeline.sh
```

Expected: exit 1 with `FAIL: AGENTS.md does not document the Sass manifest` after the asset build succeeds.

- [ ] **Step 3: Update the Frontend Assets guide**

In `AGENTS.md`, replace the opening paragraph under `## Frontend Assets` with:

```markdown
Frontend tooling uses Node 24.18.0, pinned in `.nvmrc`. Dependency declarations and resolved versions live in `package.json` and `package-lock.json`. `assets/scss/app.scss` is the Sass manifest: private tokens and mixins live under `abstracts/`, document defaults under `base/`, reusable selectors under `components/`, and page-owned rules under `pages/`. Vanilla JavaScript remains under `assets/js/`. Install and build strictly from the lockfile:
```

Keep the existing command blocks and the instruction not to edit generated files.

- [ ] **Step 4: Run the focused documentation and asset check**

Run:

```bash
bash scripts/test-asset-pipeline.sh
```

Expected: exit 0 and `PASS: asset pipeline`.

- [ ] **Step 5: Run the complete project verification suite**

Run:

```bash
npm run build
npm test
uv run python manage.py test
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Expected: the asset build completes; 3 JavaScript tests pass; all Django tests pass; Django reports no system-check issues; and Django reports `No changes detected`.

- [ ] **Step 6: Confirm scope and commit the documentation**

Run:

```bash
git status --short
git diff --check
git diff -- AGENTS.md scripts/test-asset-pipeline.sh
git add AGENTS.md scripts/test-asset-pipeline.sh
git commit -m "docs: describe modular Sass sources"
```

Expected: the diff contains only the documentation contract added in this task and the Frontend Assets paragraph. The commit succeeds, and ignored generated assets are absent from the commit.

- [ ] **Step 7: Verify the final repository state**

Run:

```bash
git status --short
git log -4 --oneline
```

Expected: the worktree is clean. The two implementation commits appear above the already committed design and implementation-plan documents.
