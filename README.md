# For PythonAnywhere

A Wagtail site developed with Python 3.13, Django 6, Wagtail 7.4, and MySQL.

## Docker Compose development

Create the ignored local environment file and start the site:

```bash
cp .env.example .env
docker compose up --build
```

Open <http://localhost:8000>. The MySQL database, uploaded media, and collected static files use named Docker volumes. On the database volume's first initialization, `scripts/init-db.sh` grants the application user access to the test database used by Django's test runner.

Run project checks in the web container:

```bash
docker compose run --rm web python manage.py test
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
```

Create a local Wagtail administrator when needed:

```bash
docker compose run --rm web python manage.py createsuperuser
```

Stop containers while preserving development data:

```bash
docker compose down
```

## Host development with UV

Host commands require Python 3.13, UV, and a reachable MySQL server configured in `.env`:

```bash
uv sync --locked
uv run python manage.py migrate
uv run python manage.py runserver
```

Dependencies are installed from `pyproject.toml` and `uv.lock`; this project does not use `requirements.txt`.

## PythonAnywhere deployment

Production deployment is started manually with **Run workflow** in the GitHub Actions workflow named **Deploy to PythonAnywhere**. The workflow validates `main`, passes its exact validated commit SHA to a guarded deployment over SSH, reloads the WSGI app, and verifies the public site.

See [the PythonAnywhere runbook](docs/pythonanywhere.md) for one-time setup, GitHub configuration, deployment operation, and recovery.
