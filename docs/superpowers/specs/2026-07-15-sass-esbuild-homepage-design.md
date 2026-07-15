# Sass, esbuild, and Placeholder Homepage Design

## Goal

Add a small, reproducible frontend asset pipeline to the Wagtail project and use it to replace Wagtail's generated welcome page with a neutral "coming soon" placeholder. The pipeline must work during local Docker development, GitHub validation, Docker image builds, and PythonAnywhere deployments.

## Scope

The change includes:

- Sass compilation for the global stylesheet.
- esbuild bundling for vanilla JavaScript.
- Minified production builds and local watch commands.
- A separate Docker Compose asset-watcher service.
- A production Docker asset-build stage.
- Node-based validation in both GitHub Actions workflows.
- Build-time Node usage in the PythonAnywhere deployment script.
- PythonAnywhere one-time NVM setup instructions.
- A static, responsive placeholder homepage with a progressively enhanced status message.
- Updates to repository guidance and automated tests.

The change does not include a JavaScript framework, Vite, editable homepage fields, a Node web server, or new Django migrations.

## Toolchain and file layout

Node.js `24.18.0` will be pinned in `.nvmrc`. The npm development dependencies will be Sass, esbuild, and concurrently, with exact resolved versions recorded in `package-lock.json`.

Source assets will live outside Django's static source tree:

```text
assets/
  js/
    app.js
  scss/
    app.scss
```

Generated files will be written to the global static paths already referenced by `app/templates/base.html`:

```text
app/static/css/app.css
app/static/js/app.js
```

The generated files will be ignored by Git. Every supported execution environment will build them before they are needed.

## npm interface

`package.json` will expose focused commands for each asset and two public workflows:

- `npm run build` compiles and minifies Sass and bundles and minifies vanilla JavaScript.
- `npm run dev` runs the Sass and esbuild watchers concurrently.

The individual CSS and JavaScript build/watch commands will remain available as named npm scripts so failures identify the responsible tool. esbuild will target broadly supported modern browsers without introducing transpilation plugins or a framework.

## Placeholder homepage

`app/home/templates/home/home_page.html` will stop loading and including Wagtail's generated welcome assets. The obsolete `welcome_page.html` template and `welcome_page.css` stylesheet will be removed.

The replacement page will be static template content with semantic HTML:

- A restrained site-name or wordmark placeholder.
- The headline "Something new is taking shape".
- Brief neutral supporting copy.
- A status indicator whose non-JavaScript text is "Site preparation in progress".
- A small footer identifying the site as powered by Wagtail.

Sass will provide a responsive centered layout, a neutral colour palette, readable typography, a contained panel, and status-indicator styling. The layout must remain usable on narrow screens and must not depend on externally hosted fonts, images, or scripts.

Vanilla JavaScript will progressively enhance the status indicator by rotating through the messages "Planning", "Building", and "Refining" with a gentle transition. The initial static message remains meaningful when JavaScript is unavailable. The enhancement must respect `prefers-reduced-motion`, and the status region must avoid repeatedly interrupting assistive technology.

No `HomePage` model fields or migrations will be added.

## Local and Docker development

Host development will support `npm ci` followed by `npm run dev`.

Docker Compose will gain a separate Node `assets` service using the pinned Node 24 line. It will install the locked npm dependencies and start `npm run dev` automatically when `docker compose up --build` runs. The service will share the repository bind mount so generated CSS and JavaScript are immediately visible to the Django web service. Its `node_modules` directory will use a dedicated named volume so container dependencies do not overwrite host dependencies.

The Django runtime container will not run a Node server. The production Dockerfile will add a Node build stage that installs dependencies with `npm ci`, runs `npm run build`, and copies the generated assets into the final Python image.

## Continuous integration

Both `.github/workflows/ci.yml` and the validation job in `.github/workflows/deploy.yml` will:

1. Set up the Node version from `.nvmrc`.
2. Enable npm dependency caching using `package-lock.json`.
3. Run `npm ci`.
4. Run `npm run build`.
5. Continue with the existing Python and Django validation.

This ensures the exact commit selected for deployment has a valid frontend build. CI will not commit or upload generated assets.

## PythonAnywhere deployment

PythonAnywhere will use Node only as a build-time tool. It will not run a Node web server.

`scripts/deploy.sh` will use the confirmed NVM installation directory:

```bash
export NVM_DIR="$HOME/nvm"
source "$NVM_DIR/nvm.sh"
nvm use
npm ci
npm run build
```

These commands will run after the checkout is fast-forwarded and Python dependencies are synchronized, but before Django's production checks, migrations, `collectstatic`, and the WSGI reload. The script's existing strict error handling will abort deployment if NVM, Node, dependency installation, or asset compilation fails. An asset failure therefore occurs before database changes and before the intentional application reload.

## PythonAnywhere one-time setup

`docs/pythonanywhere.md` will extend the one-time setup instructions with the official PythonAnywhere-compatible NVM layout at `$HOME/nvm`. The instructions will cover:

1. Cloning NVM into `$HOME/nvm` when it is not already installed.
2. Exporting `NVM_DIR` and sourcing `$NVM_DIR/nvm.sh`.
3. Changing to the repository and running `nvm install` so `.nvmrc` selects Node `24.18.0`.
4. Setting that version as the NVM default.
5. Verifying `node --version` and `npm --version`.
6. Running `npm ci` and `npm run build` before the initial `collectstatic` command.

The documentation will explain that the deployment script sources NVM itself because the GitHub-triggered SSH command uses a non-interactive shell.

## Failure behavior

- Missing NVM or the pinned Node version causes deployment to fail with a nonzero status.
- A lockfile mismatch causes `npm ci` to fail rather than changing dependency resolution on the server.
- Sass or JavaScript compilation errors stop CI, Docker image construction, or deployment in the environment where they occur.
- The homepage remains readable if JavaScript is disabled or its generated bundle cannot execute.
- Existing deployment recovery guidance remains applicable because a failed deployment may have fast-forwarded the checkout without reloading the WSGI application.

## Testing

Tests will verify behavior at the appropriate boundary:

- Django homepage tests will assert the replacement template renders its headline, fallback status text, and JavaScript enhancement hook, and that it no longer includes the Wagtail welcome page.
- The real `npm run build` command will verify that Sass and esbuild can produce both global assets from a clean dependency installation.
- Existing shell invariant tests will be extended to verify NVM sourcing, locked npm installation, asset compilation, and the required ordering before migrations, static collection, and reload.
- Workflow assertions will verify that both GitHub validation paths build the assets using `.nvmrc`.
- Docker assertions will verify the Compose watcher service and production image build stage.
- The full Django test suite, Django checks, migration-drift check, npm build, and existing deployment shell tests will run before completion.

## Repository documentation

`AGENTS.md` will be updated to describe Node `24.18.0`, npm lockfile usage, host asset commands, automatic Docker asset watching, CI asset validation, and PythonAnywhere build-time asset compilation. The guide will continue to make clear that there is no Node application server on PythonAnywhere.
