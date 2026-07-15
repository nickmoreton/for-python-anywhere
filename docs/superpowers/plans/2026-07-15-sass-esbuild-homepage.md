# Sass, esbuild, and Placeholder Homepage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible Sass and vanilla-JavaScript esbuild pipeline across host, Docker, CI, and PythonAnywhere workflows, then use it for a neutral, progressively enhanced coming-soon homepage.

**Architecture:** Sass and esbuild remain separate tools behind npm scripts, with source files under `assets/` and ignored output under Django's existing `app/static/` paths. Docker Compose runs a dedicated watcher, the production Docker image builds assets in a Node stage, CI validates the same locked build, and PythonAnywhere sources its confirmed `$HOME/nvm` installation before building and collecting static files.

**Tech Stack:** Node.js 24.18.0, npm, Sass 1.101.0, esbuild 0.28.1, concurrently 10.0.3, vanilla JavaScript, Django 6/Wagtail 7, Bash, Docker Compose, GitHub Actions.

## Global Constraints

- Pin Node.js exactly to `24.18.0` in `.nvmrc`.
- Use vanilla JavaScript only; do not add Vite or a JavaScript framework.
- Keep homepage copy static; do not add `HomePage` fields or Django migrations.
- Keep Node as a build-time and watch-time tool; do not run a Node application server.
- Keep source assets under `assets/` and generated assets at `app/static/css/app.css` and `app/static/js/app.js`.
- Do not commit generated CSS or JavaScript; build them in every supported environment.
- The fallback status text must be `Site preparation in progress`.
- The enhanced status sequence must be `Planning`, `Building`, and `Refining` and must respect `prefers-reduced-motion`.
- PythonAnywhere must source NVM from the confirmed path `$HOME/nvm`.
- Preserve all existing deployment locking, backup, exact-commit, and recovery behavior.

---

## File responsibility map

- `.nvmrc`: canonical Node version for developers, CI, Docker, and PythonAnywhere.
- `package.json` / `package-lock.json`: exact npm interface and locked tool dependencies.
- `assets/scss/app.scss`: authored global and homepage styling.
- `assets/js/app.js`: pure status helpers plus browser progressive enhancement.
- `assets/js/app.test.js`: Node built-in tests for the status sequence and reduced-motion decision.
- `app/static/css/app.css` / `app/static/js/app.js`: ignored build outputs consumed by Django and `collectstatic`.
- `app/home/templates/home/home_page.html`: semantic static placeholder content and enhancement hook.
- `app/home/tests.py`: rendered-page behavior assertions.
- `scripts/test-asset-pipeline.sh`: executable contract for the Node manifest and real production build.
- `scripts/test-container-assets.sh`: static contract for Compose watching and Docker image building.
- `scripts/test-workflow-assets.sh`: static contract for both GitHub validation workflows.
- `scripts/test-deployment-invariants.sh`: deployment ordering and runbook invariants.
- `scripts/test-deploy-failures.sh`: executable proof that npm failure aborts deployment before Django operations.
- `Dockerfile`: production frontend build stage and generated-asset copy.
- `compose.yaml`: automatic local asset watcher and isolated container `node_modules`.
- `.gitignore` / `.dockerignore`: exclude dependencies and generated assets from Git and Docker context.
- `.github/workflows/ci.yml` / `.github/workflows/deploy.yml`: build assets for every validated commit.
- `scripts/deploy.sh`: source NVM and build assets before production Django operations.
- `docs/pythonanywhere.md`: one-time NVM/Node setup and initial asset build.
- `AGENTS.md`: supported commands, structure, and workflow guidance.

---

### Task 1: Establish the locked asset pipeline

**Files:**
- Create: `.nvmrc`
- Create: `package.json`
- Create: `package-lock.json`
- Create: `assets/scss/app.scss`
- Create: `assets/js/app.js`
- Create: `scripts/test-asset-pipeline.sh`
- Modify: `.gitignore`
- Delete: `app/static/css/app.css`
- Delete: `app/static/js/app.js`

**Interfaces:**
- Consumes: Node/npm and the existing global static URLs in `app/templates/base.html`.
- Produces: `npm run build`, `npm run dev`, `npm test`, and generated `app/static/css/app.css` and `app/static/js/app.js` files for all later tasks.

- [ ] **Step 1: Write the failing asset-pipeline contract**

Create `scripts/test-asset-pipeline.sh`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

[[ -f .nvmrc ]] || fail ".nvmrc is missing"
[[ $(<.nvmrc) == 24.18.0 ]] || fail ".nvmrc does not pin Node 24.18.0"
[[ -f package-lock.json ]] || fail "package-lock.json is missing"
[[ -f assets/scss/app.scss ]] || fail "Sass entry point is missing"
[[ -f assets/js/app.js ]] || fail "JavaScript entry point is missing"

node <<'NODE'
const manifest = require('./package.json');
const expectedDependencies = {
  sass: '1.101.0',
  esbuild: '0.28.1',
  concurrently: '10.0.3',
};

if (manifest.private !== true) throw new Error('package must be private');
if (manifest.engines?.node !== '24.18.0') throw new Error('Node engine is not pinned');
for (const [name, version] of Object.entries(expectedDependencies)) {
  if (manifest.devDependencies?.[name] !== version) {
    throw new Error(`${name} is not pinned to ${version}`);
  }
}
for (const script of ['build', 'build:css', 'build:js', 'dev', 'dev:css', 'dev:js', 'test']) {
  if (!manifest.scripts?.[script]) throw new Error(`missing npm script: ${script}`);
}
NODE

grep -Fxq 'node_modules/' .gitignore || fail "node_modules is not ignored"
grep -Fxq 'app/static/css/app.css' .gitignore || fail "generated CSS is not ignored"
grep -Fxq 'app/static/js/app.js' .gitignore || fail "generated JavaScript is not ignored"

rm -f app/static/css/app.css app/static/js/app.js
npm run build
[[ -s app/static/css/app.css ]] || fail "production CSS was not generated"
[[ -s app/static/js/app.js ]] || fail "production JavaScript was not generated"

echo "PASS: asset pipeline"
```

Make it executable:

```bash
chmod +x scripts/test-asset-pipeline.sh
```

- [ ] **Step 2: Run the contract and verify it fails for the missing Node pin**

Run:

```bash
bash scripts/test-asset-pipeline.sh
```

Expected: exit 1 with `FAIL: .nvmrc is missing`.

- [ ] **Step 3: Add the pinned manifest, ignored outputs, and minimal build entries**

Create `.nvmrc`:

```text
24.18.0
```

Create `package.json`:

```json
{
  "name": "for-python-anywhere",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "engines": {
    "node": "24.18.0"
  },
  "scripts": {
    "build": "npm run build:css && npm run build:js",
    "build:css": "sass --no-source-map --style=compressed assets/scss/app.scss app/static/css/app.css",
    "build:js": "esbuild assets/js/app.js --bundle --minify --target=es2020 --outfile=app/static/js/app.js",
    "dev": "concurrently --kill-others --names css,js \"npm:dev:css\" \"npm:dev:js\"",
    "dev:css": "sass --watch --no-source-map assets/scss/app.scss app/static/css/app.css",
    "dev:js": "esbuild assets/js/app.js --bundle --target=es2020 --outfile=app/static/js/app.js --watch",
    "test": "node --test assets/js/*.test.js"
  },
  "devDependencies": {
    "concurrently": "10.0.3",
    "esbuild": "0.28.1",
    "sass": "1.101.0"
  }
}
```

Create `assets/scss/app.scss`:

```scss
:root {
  color-scheme: light;
}
```

Create `assets/js/app.js`:

```javascript
document.documentElement.classList.add("js");
```

Remove the tracked empty outputs from the Git index:

```bash
git rm app/static/css/app.css app/static/js/app.js
```

Then append these entries to `.gitignore`:

```gitignore

# Node dependencies and generated frontend assets
node_modules/
app/static/css/app.css
app/static/js/app.js
```

Generate the lockfile with the pinned manifest, then install strictly from it:

```bash
npm install --package-lock-only --ignore-scripts
npm ci
```

- [ ] **Step 4: Run the real build contract and verify it passes**

Run:

```bash
bash scripts/test-asset-pipeline.sh
```

Expected: both Sass and esbuild report generated assets and the script prints `PASS: asset pipeline`.

- [ ] **Step 5: Commit the locked pipeline**

```bash
git add .nvmrc package.json package-lock.json assets .gitignore scripts/test-asset-pipeline.sh
git commit -m "build: add Sass and esbuild pipeline"
```

---

### Task 2: Replace the Wagtail welcome page with the tested placeholder

**Files:**
- Create: `assets/js/app.test.js`
- Modify: `assets/js/app.js`
- Modify: `assets/scss/app.scss`
- Modify: `app/home/templates/home/home_page.html`
- Modify: `app/home/tests.py`
- Delete: `app/home/templates/home/welcome_page.html`
- Delete: `app/home/static/css/welcome_page.css`

**Interfaces:**
- Consumes: `npm test`, `npm run build`, and the existing `HomePage` route.
- Produces: exported `STATUS_MESSAGES`, `nextStatusIndex(currentIndex)`, and `shouldAnimate(prefersReducedMotion)` helpers plus the `[data-status-message]` enhancement hook.

- [ ] **Step 1: Write failing rendered-homepage tests**

Add these methods to `HomeTests` in `app/home/tests.py`:

```python
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
```

- [ ] **Step 2: Run the homepage tests and verify the old welcome page fails them**

Run:

```bash
uv run python manage.py test app.home.tests.HomeTests
```

Expected: the new placeholder assertions fail because the generated Wagtail welcome page is still rendered.

- [ ] **Step 3: Write failing vanilla-JavaScript unit tests**

Create `assets/js/app.test.js`:

```javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  STATUS_MESSAGES,
  nextStatusIndex,
  shouldAnimate,
} from "./app.js";

test("status messages use the approved sequence", () => {
  assert.deepEqual(STATUS_MESSAGES, ["Planning", "Building", "Refining"]);
});

test("nextStatusIndex advances and wraps", () => {
  assert.equal(nextStatusIndex(0), 1);
  assert.equal(nextStatusIndex(1), 2);
  assert.equal(nextStatusIndex(2), 0);
});

test("animation is disabled when reduced motion is preferred", () => {
  assert.equal(shouldAnimate(true), false);
  assert.equal(shouldAnimate(false), true);
});
```

- [ ] **Step 4: Run the JavaScript tests and verify the missing exports fail**

Run:

```bash
npm test
```

Expected: FAIL because `STATUS_MESSAGES`, `nextStatusIndex`, and `shouldAnimate` are not exported.

- [ ] **Step 5: Implement the semantic placeholder template**

Replace `app/home/templates/home/home_page.html` with:

```django
{% extends "base.html" %}

{% block body_class %}template-homepage{% endblock %}

{% block content %}
<main class="coming-soon">
    <section class="coming-soon__panel" aria-labelledby="coming-soon-title">
        <p class="coming-soon__brand">{{ page.title }}</p>
        <p class="coming-soon__eyebrow">A new website</p>
        <h1 id="coming-soon-title">Something new is taking shape</h1>
        <p class="coming-soon__intro">
            We are carefully preparing this space. Please check back soon.
        </p>
        <div class="status">
            <span class="status__dot" aria-hidden="true"></span>
            <span class="status__message" data-status-message>Site preparation in progress</span>
        </div>
    </section>
    <footer class="coming-soon__footer">
        Powered by <a href="https://wagtail.org/" rel="noreferrer">Wagtail</a>
    </footer>
</main>
{% endblock content %}
```

Delete `app/home/templates/home/welcome_page.html` and `app/home/static/css/welcome_page.css`.

- [ ] **Step 6: Implement the responsive Sass design**

Replace `assets/scss/app.scss` with:

```scss
$ink: #202321;
$muted: #666d68;
$line: #dfe4e0;
$surface: #ffffff;
$canvas: #f2f4f1;
$accent: #356b52;
$accent-soft: #dce9e1;

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
  background: $canvas;
}

body {
  min-height: 100vh;
  margin: 0;
  color: $ink;
  background:
    radial-gradient(circle at 20% 10%, rgba($accent, 0.08), transparent 32rem),
    $canvas;
  line-height: 1.6;
}

a {
  color: inherit;
  text-underline-offset: 0.18em;
}

a:hover {
  color: $accent;
}

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
  border: 1px solid rgba($line, 0.9);
  border-radius: 1.5rem;
  background: rgba($surface, 0.92);
  box-shadow: 0 1.5rem 4rem rgba($ink, 0.08);
}

.coming-soon__brand,
.coming-soon__eyebrow,
.coming-soon__intro,
.coming-soon h1 {
  margin-top: 0;
}

.coming-soon__brand {
  margin-bottom: clamp(3rem, 9vw, 6rem);
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.coming-soon__eyebrow {
  margin-bottom: 0.75rem;
  color: $accent;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.coming-soon h1 {
  max-width: 12ch;
  margin-bottom: 1.25rem;
  font-size: clamp(2.5rem, 8vw, 5.5rem);
  font-weight: 600;
  letter-spacing: -0.055em;
  line-height: 0.98;
}

.coming-soon__intro {
  max-width: 35rem;
  margin-bottom: 2rem;
  color: $muted;
  font-size: clamp(1rem, 2vw, 1.15rem);
}

.status {
  display: inline-flex;
  align-items: center;
  gap: 0.7rem;
  min-height: 2.5rem;
  padding: 0.55rem 0.9rem;
  border: 1px solid $accent-soft;
  border-radius: 999px;
  color: $accent;
  background: rgba($accent-soft, 0.45);
  font-size: 0.85rem;
  font-weight: 650;
}

.status__dot {
  width: 0.55rem;
  height: 0.55rem;
  flex: 0 0 auto;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 0 0 rgba($accent, 0.35);
  animation: status-pulse 2.4s ease-out infinite;
}

.status__message {
  transition: opacity 180ms ease, transform 180ms ease;
}

.status__message.is-changing {
  opacity: 0;
  transform: translateY(0.2rem);
}

.coming-soon__footer {
  color: $muted;
  font-size: 0.8rem;
  text-align: center;
}

@keyframes status-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba($accent, 0.35);
  }

  70%,
  100% {
    box-shadow: 0 0 0 0.6rem rgba($accent, 0);
  }
}

@media (max-width: 34rem) {
  .coming-soon__panel {
    border-radius: 1rem;
  }

  .coming-soon__brand {
    margin-bottom: 3rem;
  }
}

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

- [ ] **Step 7: Implement the tested vanilla-JavaScript enhancement**

Replace `assets/js/app.js` with:

```javascript
export const STATUS_MESSAGES = ["Planning", "Building", "Refining"];

export function nextStatusIndex(currentIndex) {
  return (currentIndex + 1) % STATUS_MESSAGES.length;
}

export function shouldAnimate(prefersReducedMotion) {
  return !prefersReducedMotion;
}

function enhanceStatusMessage() {
  const statusMessage = document.querySelector("[data-status-message]");
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");

  if (!statusMessage || !shouldAnimate(motionPreference.matches)) {
    return;
  }

  let currentIndex = STATUS_MESSAGES.length - 1;

  window.setInterval(() => {
    statusMessage.classList.add("is-changing");
    window.setTimeout(() => {
      currentIndex = nextStatusIndex(currentIndex);
      statusMessage.textContent = STATUS_MESSAGES[currentIndex];
      statusMessage.classList.remove("is-changing");
    }, 180);
  }, 2800);
}

if (typeof document !== "undefined") {
  document.documentElement.classList.add("js");
  enhanceStatusMessage();
}
```

- [ ] **Step 8: Run focused tests and rebuild the assets**

Run:

```bash
uv run python manage.py test app.home.tests.HomeTests
npm test
npm run build
```

Expected: all homepage and Node tests pass; Sass and esbuild produce nonempty minified files.

- [ ] **Step 9: Commit the placeholder homepage**

```bash
git add app/home assets/js/app.js assets/js/app.test.js assets/scss/app.scss
git commit -m "feat: add coming soon homepage"
```

---

### Task 3: Integrate asset builds with Docker and Compose

**Files:**
- Create: `scripts/test-container-assets.sh`
- Modify: `Dockerfile`
- Modify: `compose.yaml`
- Modify: `.dockerignore`

**Interfaces:**
- Consumes: `.nvmrc`, `package-lock.json`, `npm run build`, and `npm run dev` from Task 1.
- Produces: a production image containing both generated assets and an `assets` Compose service that watches the bind-mounted source tree.

- [ ] **Step 1: Write the failing container integration contract**

Create `scripts/test-container-assets.sh`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

rg -q '^FROM node:24\.18\.0-bookworm-slim AS frontend$' Dockerfile \
    || fail "Dockerfile is missing the pinned frontend stage"
rg -q '^RUN npm ci$' Dockerfile \
    || fail "Dockerfile does not install locked frontend dependencies"
rg -q '^RUN npm run build$' Dockerfile \
    || fail "Dockerfile does not build frontend assets"
rg -q 'COPY --from=frontend .*app/static/css/app\.css' Dockerfile \
    || fail "Dockerfile does not copy generated CSS"
rg -q 'COPY --from=frontend .*app/static/js/app\.js' Dockerfile \
    || fail "Dockerfile does not copy generated JavaScript"

rg -q '^  assets:$' compose.yaml || fail "Compose assets service is missing"
rg -q 'image: node:24\.18\.0-bookworm-slim' compose.yaml \
    || fail "Compose assets service does not use pinned Node"
rg -q 'npm ci && npm run dev' compose.yaml \
    || fail "Compose assets service does not run the watcher"
rg -q 'node-modules:/app/node_modules' compose.yaml \
    || fail "Compose assets service lacks an isolated node_modules volume"
grep -Fxq 'node_modules/' .dockerignore || fail "node_modules is not excluded from Docker context"

echo "PASS: container asset integration"
```

Make it executable:

```bash
chmod +x scripts/test-container-assets.sh
```

- [ ] **Step 2: Run the contract and verify the frontend stage is missing**

Run:

```bash
bash scripts/test-container-assets.sh
```

Expected: exit 1 with `FAIL: Dockerfile is missing the pinned frontend stage`.

- [ ] **Step 3: Add the production frontend stage**

Insert this stage at the start of `Dockerfile`, before the UV stage:

```dockerfile
FROM node:24.18.0-bookworm-slim AS frontend

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY assets ./assets
RUN npm run build

```

After the existing final `COPY --chown=wagtail:wagtail . .`, copy the generated files from the frontend stage:

```dockerfile
COPY --from=frontend --chown=wagtail:wagtail /app/app/static/css/app.css /app/app/static/css/app.css
COPY --from=frontend --chown=wagtail:wagtail /app/app/static/js/app.js /app/app/static/js/app.js
```

- [ ] **Step 4: Add the automatic Compose watcher**

Add this service under `services:` in `compose.yaml`:

```yaml
  assets:
    image: node:24.18.0-bookworm-slim
    init: true
    working_dir: /app
    command: sh -c "npm ci && npm run dev"
    volumes:
      - .:/app
      - node-modules:/app/node_modules
```

Add the named volume under `volumes:`:

```yaml
  node-modules:
```

Append this entry to `.dockerignore`:

```dockerignore
node_modules/
```

- [ ] **Step 5: Run the static contract and build the production image**

Run:

```bash
bash scripts/test-container-assets.sh
docker compose build web
```

Expected: the contract prints `PASS: container asset integration`; the Docker build completes after the frontend and Python stages.

- [ ] **Step 6: Confirm Compose resolves the watcher configuration**

Run:

```bash
docker compose config --quiet
```

Expected: exit 0 with no configuration errors.

- [ ] **Step 7: Commit the container integration**

```bash
git add Dockerfile compose.yaml .dockerignore scripts/test-container-assets.sh
git commit -m "build: compile frontend assets in Docker"
```

---

### Task 4: Validate the locked asset build in both GitHub workflows

**Files:**
- Create: `scripts/test-workflow-assets.sh`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes: `.nvmrc`, `package-lock.json`, and `npm run build` from Task 1.
- Produces: identical Node setup, dependency installation, and asset validation in feature-branch CI and pre-deployment validation.

- [ ] **Step 1: Write the failing workflow contract**

Create `scripts/test-workflow-assets.sh`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

for workflow in .github/workflows/ci.yml .github/workflows/deploy.yml; do
    rg -q 'uses: actions/setup-node@v4' "$workflow" \
        || fail "$workflow does not set up Node"
    rg -q 'node-version-file: \.nvmrc' "$workflow" \
        || fail "$workflow does not read .nvmrc"
    rg -q 'cache: npm' "$workflow" \
        || fail "$workflow does not cache npm downloads"
    rg -q 'run: npm ci' "$workflow" \
        || fail "$workflow does not use npm ci"
    rg -q 'run: npm run build' "$workflow" \
        || fail "$workflow does not build assets"
done

echo "PASS: workflow asset integration"
```

Make it executable:

```bash
chmod +x scripts/test-workflow-assets.sh
```

- [ ] **Step 2: Run the contract and verify feature-branch CI lacks Node setup**

Run:

```bash
bash scripts/test-workflow-assets.sh
```

Expected: exit 1 with `.github/workflows/ci.yml does not set up Node`.

- [ ] **Step 3: Add the asset build to feature-branch CI**

In `.github/workflows/ci.yml`, immediately after `Check out pushed commit`, add:

```yaml
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version-file: .nvmrc
          cache: npm

      - name: Install frontend dependencies
        run: npm ci

      - name: Build frontend assets
        run: npm run build
```

- [ ] **Step 4: Add the asset build to deployment validation**

In the `validate` job of `.github/workflows/deploy.yml`, immediately after `Capture validated commit`, add:

```yaml
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version-file: .nvmrc
          cache: npm

      - name: Install frontend dependencies
        run: npm ci

      - name: Build frontend assets
        run: npm run build
```

- [ ] **Step 5: Run the workflow contract and verify it passes**

Run:

```bash
bash scripts/test-workflow-assets.sh
```

Expected: `PASS: workflow asset integration`.

- [ ] **Step 6: Commit workflow validation**

```bash
git add .github/workflows/ci.yml .github/workflows/deploy.yml scripts/test-workflow-assets.sh
git commit -m "ci: validate frontend asset builds"
```

---

### Task 5: Build assets safely during PythonAnywhere deployment

**Files:**
- Modify: `scripts/test-deployment-invariants.sh`
- Modify: `scripts/test-deploy-failures.sh`
- Modify: `scripts/deploy.sh`
- Modify: `docs/pythonanywhere.md`

**Interfaces:**
- Consumes: `.nvmrc`, the confirmed `$HOME/nvm/nvm.sh`, `npm ci`, and `npm run build`.
- Produces: deployment ordering that aborts before Django checks/migrations/static collection/reload on asset failure, plus repeatable one-time host setup instructions.

- [ ] **Step 1: Add failing static deployment and runbook invariants**

Append this block before the final PASS line in `scripts/test-deployment-invariants.sh`:

```bash
rg -q '^export NVM_DIR="\$HOME/nvm"$' scripts/deploy.sh \
    || fail "deployment does not use the confirmed NVM directory"
rg -q '^source "\$NVM_DIR/nvm\.sh"$' scripts/deploy.sh \
    || fail "deployment does not source NVM"

deploy_nvm_line=$(rg -n '^source "\$NVM_DIR/nvm\.sh"$' scripts/deploy.sh | cut -d: -f1)
deploy_ci_line=$(rg -n '^npm ci$' scripts/deploy.sh | cut -d: -f1)
deploy_build_line=$(rg -n '^npm run build$' scripts/deploy.sh | cut -d: -f1)
deploy_migrate_line=$(rg -n '^uv run python manage\.py migrate ' scripts/deploy.sh | cut -d: -f1)
deploy_collectstatic_line=$(rg -n '^uv run python manage\.py collectstatic ' scripts/deploy.sh | cut -d: -f1)
deploy_reload_line=$(rg -n '^touch "\$wsgi_file"$' scripts/deploy.sh | cut -d: -f1)

(( deploy_nvm_line < deploy_ci_line \
    && deploy_ci_line < deploy_build_line \
    && deploy_build_line < deploy_migrate_line \
    && deploy_build_line < deploy_collectstatic_line \
    && deploy_build_line < deploy_reload_line )) \
    || fail "frontend build is not ordered before Django mutation and reload"

rg -q 'git clone --depth 1 https://github\.com/nvm-sh/nvm\.git "\$HOME/nvm"' docs/pythonanywhere.md \
    || fail "runbook does not document NVM installation"
rg -q '^nvm install$' docs/pythonanywhere.md \
    || fail "runbook does not install the .nvmrc version"
rg -q '^npm ci$' docs/pythonanywhere.md \
    || fail "runbook does not install locked frontend dependencies"
rg -q '^npm run build$' docs/pythonanywhere.md \
    || fail "runbook does not build initial frontend assets"
```

- [ ] **Step 2: Add a failing executable npm-failure test**

In `setup_case` in `scripts/test-deploy-failures.sh`, replace the existing `uv` mock with the logging version below, then create the expected NVM file and npm mock:

```bash
    mkdir -p "$home/nvm"
    cat > "$home/nvm/nvm.sh" <<'NVM'
nvm() {
    printf "nvm %s\n" "$*" >> "$COMMAND_LOG"
    return "${NVM_EXIT:-0}"
}
NVM
    make_command "$bin/uv" 'printf "uv %s\n" "$*" >> "$COMMAND_LOG"' 'exit 0'
    make_command "$bin/npm" \
        'printf "npm %s\n" "$*" >> "$COMMAND_LOG"' \
        'if [[ "$*" == "run build" ]]; then exit "${NPM_BUILD_EXIT:-0}"; fi' \
        'exit 0'
```

Pass `NPM_BUILD_EXIT` through `run_deploy`:

```bash
        NPM_BUILD_EXIT=${NPM_BUILD_EXIT:-0} \
```

Add this test function:

```bash
test_npm_build_failure_aborts_before_django_operations() {
    setup_case
    NPM_BUILD_EXIT=49 run_deploy
    [[ $status == 49 ]] || fail "npm build failure returned $status: $output"
    grep -q '^npm ci$' "$log" || fail "deployment did not install locked npm dependencies"
    grep -q '^npm run build$' "$log" || fail "deployment did not attempt the asset build"
    ! grep -q '^uv run python manage.py' "$log" \
        || fail "deployment ran Django operations after asset build failure"
    [[ ! -e "$repository/wsgi.py.reloaded" ]] \
        || fail "deployment reloaded WSGI after asset build failure"
    rm -rf "$case_dir"
    echo "PASS: npm build failure aborts before Django operations"
}
```

The WSGI reload remains observable through the existing `touch` call by adding this `touch` mock in `setup_case`:

```bash
    make_command "$bin/touch" '/usr/bin/touch "$@"' '[[ "$1" == */wsgi.py ]] && /usr/bin/touch "$1.reloaded"'
```

Add `npm-build` to the case selector and call the test from `all`:

```bash
    npm-build) test_npm_build_failure_aborts_before_django_operations ;;
```

```bash
        test_npm_build_failure_aborts_before_django_operations
```

- [ ] **Step 3: Run both deployment tests and verify the new invariants fail**

Run:

```bash
bash scripts/test-deployment-invariants.sh
bash scripts/test-deploy-failures.sh npm-build
```

Expected: the static test fails with `deployment does not use the confirmed NVM directory`; the executable test fails because npm is not called.

- [ ] **Step 4: Add the PythonAnywhere asset build to the deployment script**

In `scripts/deploy.sh`, insert this block after `uv sync --locked --python 3.13` and before the production Django check:

```bash
export NVM_DIR="$HOME/nvm"
source "$NVM_DIR/nvm.sh"
nvm use
npm ci
npm run build
```

- [ ] **Step 5: Document one-time NVM and asset setup**

In the `One-time PythonAnywhere setup` section of `docs/pythonanywhere.md`, after verifying Python and UV, add:

````markdown
Install NVM in the path used by the noninteractive deployment script. Skip the clone command when `$HOME/nvm/nvm.sh` already exists:

```bash
git clone --depth 1 https://github.com/nvm-sh/nvm.git "$HOME/nvm"
export NVM_DIR="$HOME/nvm"
source "$NVM_DIR/nvm.sh"
```

After cloning the repository, install its pinned Node version and make it the default for interactive consoles:

```bash
cd "$HOME/for-python-anywhere"
export NVM_DIR="$HOME/nvm"
source "$NVM_DIR/nvm.sh"
nvm install
nvm alias default "$(cat .nvmrc)"
node --version
npm --version
npm ci
npm run build
```

`node --version` must print `v24.18.0`. The deployment script sources NVM explicitly because the GitHub-triggered SSH command runs a noninteractive shell and does not rely on `.bashrc`.
````

In the initial database/static setup command block, ensure `npm ci` and `npm run build` appear immediately before `collectstatic`:

```bash
npm ci
npm run build
uv run python manage.py collectstatic --noinput --clear --settings=app.settings.production
```

- [ ] **Step 6: Run deployment tests and verify old guarantees still pass**

Run:

```bash
bash scripts/test-deployment-invariants.sh
bash scripts/test-deploy-failures.sh
```

Expected: `PASS: deployment static invariants`, the new npm-failure PASS line, and all pre-existing failure-case PASS lines.

- [ ] **Step 7: Commit PythonAnywhere integration**

```bash
git add scripts/deploy.sh scripts/test-deployment-invariants.sh scripts/test-deploy-failures.sh docs/pythonanywhere.md
git commit -m "build: compile assets during deployment"
```

---

### Task 6: Update repository guidance and run full verification

**Files:**
- Modify: `scripts/test-asset-pipeline.sh`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: every command and workflow established in Tasks 1–5.
- Produces: accurate contributor guidance and final evidence that frontend, backend, Docker, CI, and deployment contracts agree.

- [ ] **Step 1: Add a failing documentation contract**

Append this block before the final PASS line in `scripts/test-asset-pipeline.sh`:

```bash
rg -q 'Node 24\.18\.0' AGENTS.md || fail "AGENTS.md does not document the Node version"
rg -q 'npm ci' AGENTS.md || fail "AGENTS.md does not document locked npm installation"
rg -q 'npm run dev' AGENTS.md || fail "AGENTS.md does not document the watch workflow"
rg -q 'npm run build' AGENTS.md || fail "AGENTS.md does not document the production build"
rg -q 'assets service' AGENTS.md || fail "AGENTS.md does not document automatic Compose watching"
```

- [ ] **Step 2: Run the documentation contract and verify the obsolete guidance fails**

Run:

```bash
bash scripts/test-asset-pipeline.sh
```

Expected: exit 1 with `FAIL: AGENTS.md does not document the Node version`.

- [ ] **Step 3: Update the repository guide with the supported frontend workflow**

Make these exact content changes to `AGENTS.md`:

1. Replace the statement that there is no Node build step with a structure description for `assets/`, `package.json`, `package-lock.json`, `.nvmrc`, and generated `app/static/` files.
2. Add a `Frontend Assets` section containing:

````markdown
## Frontend Assets

Frontend tooling uses Node 24.18.0, pinned in `.nvmrc`. Sass and vanilla JavaScript sources live under `assets/`; npm builds ignored outputs at `app/static/css/app.css` and `app/static/js/app.js`. Install and build strictly from the lockfile:

```bash
nvm use
npm ci
npm run build
```

For active host development, run the Sass and esbuild watchers with:

```bash
npm run dev
```

Do not edit generated files directly and do not add Vite or a JavaScript framework without an explicit project decision.
````

3. Add this paragraph to `Docker Compose Development`:

```markdown
The `assets` service runs `npm run dev` automatically and writes generated assets through the shared repository bind mount. Its `node-modules` named volume keeps container-installed packages separate from host packages.
```

4. Add this paragraph to `PythonAnywhere Deployment`:

```markdown
During deployment, the remote script sources NVM from `$HOME/nvm`, installs locked frontend dependencies with `npm ci`, runs `npm run build`, and then collects the generated files with Django. Node is a build tool only and does not serve the website.
```

5. Add this verification block after the existing Django/Wagtail check commands:

```bash
bash scripts/test-asset-pipeline.sh
bash scripts/test-container-assets.sh
bash scripts/test-workflow-assets.sh
bash scripts/test-deployment-invariants.sh
bash scripts/test-deploy-failures.sh
```

- [ ] **Step 4: Run all frontend and integration contracts**

Run:

```bash
bash scripts/test-asset-pipeline.sh
npm test
bash scripts/test-container-assets.sh
bash scripts/test-workflow-assets.sh
bash scripts/test-deployment-invariants.sh
bash scripts/test-deploy-failures.sh
docker compose config --quiet
```

Expected: every script prints its PASS line, Node tests pass, and Compose configuration exits 0.

- [ ] **Step 5: Run all Django verification against Compose MySQL**

Run:

```bash
docker compose run --rm web python manage.py test
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
```

Expected: the Django test suite and system check pass, and migration drift reports `No changes detected`.

- [ ] **Step 6: Build the final production container**

Run:

```bash
docker compose build web
```

Expected: Docker completes the Node asset stage and Python runtime stage without errors.

- [ ] **Step 7: Inspect the final diff and generated-file status**

Run:

```bash
git diff --check
git status --short --ignored
```

Expected: no whitespace errors; generated `app/static/css/app.css`, `app/static/js/app.js`, and `node_modules/` appear only as ignored files, with no unrelated changes.

- [ ] **Step 8: Commit the repository guidance**

```bash
git add AGENTS.md scripts/test-asset-pipeline.sh
git commit -m "docs: document frontend build workflow"
```
