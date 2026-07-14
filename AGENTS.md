# Repository Guidelines

## Project Structure & Module Organization

This is a Wagtail site built on Django. Run project commands from the repository root, where `manage.py` lives.

- `app/settings/` contains shared, development, and production settings. `manage.py` defaults to `app.settings.dev`; pass `--settings=app.settings.production` when explicitly checking production configuration.
- `app/home/` defines the `HomePage`, its migrations, templates, app-specific static files, and the current test suite.
- `app/search/` contains the search view and template.
- `app/templates/` and `app/static/` hold site-wide templates, CSS, and JavaScript. There is no Node build step; edit these assets directly.
- `app/urls.py` wires Django admin, Wagtail admin, documents, search, and page-serving routes. `app/wsgi.py` exposes the deployment entry point.
- `media/` contains local uploaded files, while collected static output is generated under `staticfiles/`. Both are ignored by Git.
- `compose.yaml` runs the local Wagtail and MySQL services; `.env.example` documents their shared configuration.
- `scripts/start-dev.sh` starts the Compose web service, `scripts/init-db.sh` grants its MySQL user test-database access on first initialization, and `scripts/deploy.sh` performs guarded PythonAnywhere deployments.
- `.github/workflows/deploy.yml` validates and manually deploys `main` to PythonAnywhere at the exact validated commit.

## Backend Build, Test, and Development

Host development uses UV with Python 3.13. Python dependencies and resolved versions live in `pyproject.toml` and `uv.lock`; the same lockfile is used by Docker, CI, and PythonAnywhere. Host Django commands require a reachable MySQL database configured with the variables documented in `.env.example`. From the repository root:

```bash
uv sync --locked
uv run python manage.py migrate
uv run python manage.py runserver
```

Run the Django/Wagtail tests and project checks with:

```bash
uv run python manage.py test
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

When changing page models, create migrations with `uv run python manage.py makemigrations`, review the generated files under the relevant app, then run `migrate` and `test`. No coverage, lint, type-check, or documentation tool is configured; do not invent commands for them.

## Docker Compose Development

Docker is the primary local-development workflow. It uses the same Python 3.13 runtime, UV lockfile, MySQL database family, and environment-variable contract as PythonAnywhere:

```bash
cp .env.example .env
docker compose up --build
```

Run checks against the Compose MySQL service with:

```bash
docker compose run --rm web python manage.py test
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
```

The Compose MySQL service uses a persistent named volume. On first initialization, `scripts/init-db.sh` grants the application user access to Django's test database. Uploaded media and collected static files also use named volumes.

The Docker image installs dependencies directly from `pyproject.toml` and `uv.lock`; `requirements.txt` is not used.

## PythonAnywhere Deployment

PythonAnywhere runs the project directly from its UV-managed `.venv`; Docker is not used on the host. Production deployment is manually triggered by the `Deploy to PythonAnywhere` GitHub Actions workflow. The workflow validates `main` against MySQL, records its exact commit SHA, connects over SSH with a strictly verified known host, runs `scripts/deploy.sh`, reloads the WSGI app, and verifies the public URL. See `docs/pythonanywhere.md` for bootstrap, GitHub variables and secrets, deployment operation, and recovery.

## Maintaining This Guide

If development changes the structure, supported commands, dependency management, runtime configuration, or workflows above, remind the user that `AGENTS.md` should be updated. That reminder alone does not authorize editing this file outside the current task.
