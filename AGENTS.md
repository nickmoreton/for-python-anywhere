# Repository Guidelines

## Project Structure & Module Organization

This is a Wagtail site built on Django. Run project commands from the repository root, where `manage.py` lives.

- `app/settings/` contains shared, development, and production settings. `manage.py` defaults to `app.settings.dev`; pass `--settings=app.settings.production` when explicitly checking production configuration.
- `app/home/` defines the `HomePage`, its migrations, templates, app-specific static files, and the current test suite.
- `app/search/` contains the search view and template.
- `app/templates/` and `app/static/` hold site-wide templates, CSS, and JavaScript. There is no Node build step; edit these assets directly.
- `app/urls.py` wires Django admin, Wagtail admin, documents, search, and page-serving routes. `app/wsgi.py` exposes the deployment entry point.
- `db.sqlite3` and `media/` are local runtime data; collected static output is generated. These are ignored by Git.

## Backend Build, Test, and Development

Host development uses UV. The Python requirement is defined in `.python-version` and `pyproject.toml`; Python dependencies and resolved versions live in `pyproject.toml` and `uv.lock`. From the repository root:

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

## Container Deployment

`Dockerfile` is the deployment workflow and uses `requirements.txt` for its container environment; keep that path distinct from host-side UV dependency management. The image collects static files at build time, then migrates and starts Gunicorn when run:

```bash
docker build -t for-python-anywhere .
docker run --rm -p 8000:8000 for-python-anywhere
```

Consult the `Dockerfile` and `requirements.txt` for current container runtime and framework constraints rather than copying version numbers into documentation.

## Maintaining This Guide

If development changes the structure, supported commands, dependency management, runtime configuration, or workflows above, remind the user that `AGENTS.md` should be updated. That reminder alone does not authorize editing this file outside the current task.
