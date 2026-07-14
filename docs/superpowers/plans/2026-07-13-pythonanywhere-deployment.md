# PythonAnywhere Deployment Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python 3.13, MySQL-backed local Docker Compose environment and a manually triggered GitHub Actions deployment to PythonAnywhere over SSH.

**Architecture:** Django reads one environment-variable contract through `django-environ`; Compose supplies local values to a Python 3.13 web container and MySQL service, while PythonAnywhere supplies production values from an ignored `.env`. GitHub Actions validates the exact `main` revision against MySQL, invokes a strict remote deployment script over OpenSSH, and then checks the public site.

**Tech Stack:** Python 3.13, Django 6, Wagtail 7.4, UV, `django-environ`, `mysqlclient`, MySQL 8.0, Docker Compose, Bash, GitHub Actions, PythonAnywhere WSGI.

## Global Constraints

- Python is exactly 3.13 in `.python-version`, both Docker stages, GitHub Actions, and PythonAnywhere.
- Docker is for local development only; PythonAnywhere runs the UV-managed `.venv` directly.
- Docker, host development, CI, and PythonAnywhere use `pyproject.toml` and `uv.lock` as the single dependency source; `requirements.txt` is removed.
- Local, CI, and production use MySQL and the same Django environment-variable names.
- Deployment is triggered only by GitHub Actions `workflow_dispatch` and always deploys `origin/main`.
- The one-time PythonAnywhere web app, database, WSGI, static/media mappings, secrets, and SSH setup remain manual.
- Production secrets and private keys must never be committed.
- Remote Git updates are fast-forward-only; deployment does not perform destructive resets or automatic database rollback.
- Retain the five most recent pre-migration MySQL deployment backups.

## File Map

- `.python-version`: pins UV and local tooling to Python 3.13.
- `pyproject.toml` and `uv.lock`: define and lock dependencies for Docker, host development, CI, and PythonAnywhere.
- `app/settings/base.py`: owns the shared environment contract and MySQL configuration.
- `app/settings/dev.py`: owns development-only email behavior.
- `app/settings/production.py`: owns production-only static and cookie security settings.
- `app/home/tests_settings.py`: verifies the shared settings contract.
- `.env.example`: documents safe local defaults and all required variable names.
- `.gitignore`: excludes local configuration and generated static output.
- `.dockerignore`: excludes host environments, secrets, and runtime data from the Docker build context.
- `Dockerfile`: builds the Python 3.13 application image without production deployment side effects.
- `compose.yaml`: orchestrates the local web and MySQL services.
- `scripts/start-dev.sh`: performs local startup migrations/static collection and starts the development server.
- `scripts/deploy.sh`: performs the locked, backed-up, fast-forward-only PythonAnywhere deployment.
- `.github/workflows/deploy.yml`: validates and manually deploys `main`.
- `README.md`: gives the local quick start and links to deployment operations.
- `docs/pythonanywhere.md`: documents bootstrap, secrets, first deployment, operation, and recovery.
- `AGENTS.md`: documents the updated Python, UV, Compose, MySQL, and deployment workflows for future repository work.

---

### Task 1: Standardize Python and Dependency Contracts

**Files:**
- Modify: `.python-version`
- Modify: `pyproject.toml:6-9`
- Modify: `uv.lock`
- Delete: `requirements.txt`
- Modify: `Dockerfile:1-58`

**Interfaces:**
- Consumes: the existing Wagtail 7.4 and Django 6 constraints.
- Produces: Python 3.13 plus importable `environ` and `MySQLdb` modules for settings, Compose, CI, and production.

- [ ] **Step 1: Run consistency assertions and verify the current repository fails them**

```bash
test "$(tr -d '\n' < .python-version)" = "3.13"
rg -c '^FROM python:3\.13-slim-bookworm' Dockerfile | rg '^2$'
rg -q 'django-environ' pyproject.toml
rg -q 'mysqlclient' pyproject.toml
rg -q 'uv sync --locked' Dockerfile
test ! -e requirements.txt
```

Expected: at least the first assertion fails because the repository currently pins Python 3.14 and Docker uses Python 3.12.

- [ ] **Step 2: Update the runtime and dependency declarations**

Set `.python-version` to:

```text
3.13
```

Set the relevant `pyproject.toml` section to:

```toml
requires-python = ">=3.13,<3.14"
dependencies = [
    "django-environ>=0.12,<0.13",
    "gunicorn==25.1.0",
    "mysqlclient>=2.2,<3",
    "wagtail>=7.4.2,<7.5",
]
```

Remove `requirements.txt`:

```bash
git rm requirements.txt
```

Set `Dockerfile` to:

```dockerfile
FROM ghcr.io/astral-sh/uv:0.11.28 AS uv

FROM python:3.13-slim-bookworm AS builder

RUN apt-get update --yes --quiet && apt-get install --yes --quiet --no-install-recommends \
    build-essential \
    libpq-dev \
    libmariadb-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libwebp-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project --python 3.13

FROM python:3.13-slim-bookworm AS runtime

RUN apt-get update --yes --quiet && apt-get install --yes --quiet --no-install-recommends \
    libpq5 \
    libmariadb3 \
    libjpeg62-turbo \
    libwebp7 \
 && rm -rf /var/lib/apt/lists/*

RUN useradd wagtail

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PATH="/opt/venv/bin:$PATH"

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

RUN chown wagtail:wagtail /app

COPY --chown=wagtail:wagtail . .

USER wagtail

RUN python manage.py collectstatic --noinput --clear

CMD set -xe; python manage.py migrate --noinput; gunicorn app.wsgi:application
```

- [ ] **Step 3: Regenerate the UV lockfile on Python 3.13**

```bash
uv lock --python 3.13
```

Expected: exit 0 and `uv.lock` records the Python 3.13 range plus `django-environ`, Gunicorn, MySQL client, and Wagtail dependencies.

- [ ] **Step 4: Verify runtime and dependency consistency**

```bash
test "$(tr -d '\n' < .python-version)" = "3.13"
test "$(rg -c '^FROM python:3\.13-slim-bookworm' Dockerfile)" = "2"
test ! -e requirements.txt
rg -q 'COPY pyproject.toml uv.lock' Dockerfile
rg -q 'uv sync --locked --no-dev --no-install-project --python 3.13' Dockerfile
rg -q 'UV_PROJECT_ENVIRONMENT=/opt/venv' Dockerfile
! rg -q 'requirements\.txt|pip install' Dockerfile
uv sync --locked --python 3.13
uv run python -c "import environ, MySQLdb; print('dependency imports pass')"
```

Expected: every command exits 0 and prints `dependency imports pass`.

- [ ] **Step 5: Commit the runtime contract**

```bash
git add .python-version pyproject.toml uv.lock Dockerfile
git add -u requirements.txt
git commit -m "Align runtime with PythonAnywhere"
```

---

### Task 2: Implement the Environment-Driven MySQL Settings Contract

**Files:**
- Create: `app/home/tests_settings.py`
- Create: `.env.example`
- Modify: `.gitignore`
- Modify: `app/settings/base.py:13-17,85-93,173-175`
- Modify: `app/settings/dev.py`
- Modify: `app/settings/production.py`

**Interfaces:**
- Consumes: `django-environ` and `mysqlclient` from Task 1.
- Produces: settings named `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASES`, and `WAGTAILADMIN_BASE_URL`, populated from the documented environment variables.

- [ ] **Step 1: Add a settings contract test**

Create `app/home/tests_settings.py`:

```python
import os

from django.conf import settings
from django.test import SimpleTestCase


class EnvironmentSettingsTests(SimpleTestCase):
    def test_mysql_settings_match_environment(self):
        database = settings.DATABASES["default"]

        self.assertEqual(database["ENGINE"], "django.db.backends.mysql")
        self.assertEqual(database["NAME"], os.environ["MYSQL_DATABASE"])
        self.assertEqual(database["USER"], os.environ["MYSQL_USER"])
        self.assertEqual(database["PASSWORD"], os.environ["MYSQL_PASSWORD"])
        self.assertEqual(database["HOST"], os.environ["MYSQL_HOST"])
        self.assertEqual(database["PORT"], int(os.environ["MYSQL_PORT"]))
        self.assertEqual(database["OPTIONS"], {"charset": "utf8mb4"})

    def test_web_security_settings_match_environment(self):
        self.assertEqual(settings.SECRET_KEY, os.environ["DJANGO_SECRET_KEY"])
        self.assertEqual(settings.ALLOWED_HOSTS, ["localhost", "127.0.0.1"])
        self.assertEqual(
            settings.CSRF_TRUSTED_ORIGINS,
            ["http://localhost:8000"],
        )
        self.assertEqual(
            settings.WAGTAILADMIN_BASE_URL,
            os.environ["WAGTAILADMIN_BASE_URL"],
        )
        self.assertEqual(settings.STATIC_ROOT, settings.BASE_DIR / "staticfiles")
```

- [ ] **Step 2: Run the test against explicit environment values and verify it fails**

```bash
DJANGO_SECRET_KEY=local-test-secret-key-with-at-least-fifty-characters \
DJANGO_DEBUG=true \
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000 \
MYSQL_DATABASE=wagtail \
MYSQL_USER=wagtail \
MYSQL_PASSWORD=wagtail \
MYSQL_HOST=127.0.0.1 \
MYSQL_PORT=3306 \
WAGTAILADMIN_BASE_URL=http://localhost:8000 \
uv run python manage.py test app.home.tests_settings
```

Expected: FAIL because the current base settings still configure SQLite and the development secret is hard-coded.

- [ ] **Step 3: Implement the shared settings contract**

In `app/settings/base.py`, import and initialize `django-environ` immediately after defining `BASE_DIR`:

```python
from pathlib import Path

import environ


PROJECT_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = PROJECT_DIR.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    MYSQL_PORT=(int, 3306),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")
```

Replace `DATABASES` with:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("MYSQL_DATABASE"),
        "USER": env("MYSQL_USER"),
        "PASSWORD": env("MYSQL_PASSWORD"),
        "HOST": env("MYSQL_HOST"),
        "PORT": env("MYSQL_PORT"),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}
```

Replace the hard-coded Wagtail URL with:

```python
WAGTAILADMIN_BASE_URL = env("WAGTAILADMIN_BASE_URL")
```

Set the collected-static destination to the path used by Compose and PythonAnywhere:

```python
STATIC_ROOT = BASE_DIR / "staticfiles"
```

Set `app/settings/dev.py` to:

```python
from .base import *

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
```

Set `app/settings/production.py` to:

```python
from .base import *

DEBUG = False

STORAGES["staticfiles"]["BACKEND"] = (
    "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
)

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
```

- [ ] **Step 4: Document the local environment and ignore generated state**

Create `.env.example`:

```dotenv
DJANGO_SECRET_KEY=local-development-secret-key-not-for-production-use
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000
MYSQL_DATABASE=wagtail
MYSQL_USER=wagtail
MYSQL_PASSWORD=wagtail
MYSQL_HOST=db
MYSQL_PORT=3306
MYSQL_ROOT_PASSWORD=local-root-password
WAGTAILADMIN_BASE_URL=http://localhost:8000
```

Append these entries to `.gitignore`:

```gitignore

# Environment and generated static files
.env
staticfiles/
```

- [ ] **Step 5: Run the focused test and production checks**

```bash
DJANGO_SECRET_KEY=local-test-secret-key-with-at-least-fifty-characters \
DJANGO_DEBUG=true \
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000 \
MYSQL_DATABASE=wagtail \
MYSQL_USER=wagtail \
MYSQL_PASSWORD=wagtail \
MYSQL_HOST=127.0.0.1 \
MYSQL_PORT=3306 \
WAGTAILADMIN_BASE_URL=http://localhost:8000 \
uv run python manage.py test app.home.tests_settings

DJANGO_SECRET_KEY=production-check-secret-key-with-at-least-fifty-characters \
DJANGO_DEBUG=false \
DJANGO_ALLOWED_HOSTS=example.pythonanywhere.com \
DJANGO_CSRF_TRUSTED_ORIGINS=https://example.pythonanywhere.com \
MYSQL_DATABASE=account\$wagtail \
MYSQL_USER=account \
MYSQL_PASSWORD=production-check-password \
MYSQL_HOST=account.mysql.pythonanywhere-services.com \
MYSQL_PORT=3306 \
WAGTAILADMIN_BASE_URL=https://example.pythonanywhere.com \
uv run python manage.py check --deploy --settings=app.settings.production
```

Expected: the focused tests pass; the production check exits 0, with any remaining deployment warnings reviewed rather than ignored.

- [ ] **Step 6: Commit the settings contract**

```bash
git add .env.example .gitignore app/settings/base.py app/settings/dev.py app/settings/production.py app/home/tests_settings.py
git commit -m "Configure Django from the environment"
```

---

### Task 3: Add the Local Docker Compose Environment

**Files:**
- Create: `compose.yaml`
- Create: `.dockerignore`
- Create: `scripts/start-dev.sh`
- Modify: `Dockerfile:60-86`

**Interfaces:**
- Consumes: `.env`, the Task 2 settings names, and the shared UV lockfile from Task 1.
- Produces: Compose services named `web` and `db`, plus an executable `/app/scripts/start-dev.sh` container command.

- [ ] **Step 1: Verify Compose is not configured yet**

```bash
docker compose config
```

Expected: non-zero exit because no Compose configuration exists.

- [ ] **Step 2: Add the development startup script and safe Docker context**

Create `scripts/start-dev.sh`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear
exec python manage.py runserver 0.0.0.0:8000
```

Make it executable:

```bash
chmod +x scripts/start-dev.sh
```

Create `.dockerignore`:

```gitignore
.env
.git
.venv
__pycache__/
*.py[cod]
db.sqlite3
media/
staticfiles/
```

- [ ] **Step 3: Add the Compose services**

Create `compose.yaml`:

```yaml
services:
  db:
    image: mysql:8.0
    restart: unless-stopped
    env_file:
      - .env
    environment:
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_USER: ${MYSQL_USER}
    healthcheck:
      test: ["CMD-SHELL", "mysqladmin ping -h localhost -u root -p$${MYSQL_ROOT_PASSWORD}"]
      interval: 5s
      timeout: 5s
      retries: 20
    volumes:
      - mysql-data:/var/lib/mysql

  web:
    build:
      context: .
    init: true
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
    command: /app/scripts/start-dev.sh
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - media:/app/media
      - staticfiles:/app/staticfiles

volumes:
  media:
  mysql-data:
  staticfiles:
```

- [ ] **Step 4: Remove build-time and production-start side effects from the local image**

In `Dockerfile`, leave the file unchanged through `COPY --from=builder /opt/venv /opt/venv`, then replace every subsequent line with:

```dockerfile
WORKDIR /app

RUN mkdir -p /app/media /app/staticfiles \
 && chown -R wagtail:wagtail /app

COPY --chown=wagtail:wagtail . .

USER wagtail

CMD ["gunicorn", "app.wsgi:application"]
```

This removes the build-time `collectstatic` command because settings now require runtime environment values and Compose performs collection during startup.

- [ ] **Step 5: Build and exercise the Compose environment**

```bash
test -f .env || cp .env.example .env
docker compose config --quiet
docker compose build web
docker compose up -d db
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py test
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose up -d web
curl --fail --retry 10 --retry-delay 2 http://localhost:8000/
docker compose down
```

Expected: the image builds, MySQL becomes healthy, checks and tests pass, no migration drift is reported, and the homepage returns HTTP success. Named volumes remain for subsequent local runs.

- [ ] **Step 6: Commit the Compose environment**

```bash
git add .dockerignore Dockerfile compose.yaml scripts/start-dev.sh
git commit -m "Add MySQL Docker Compose development"
```

---

### Task 4: Add the PythonAnywhere Deployment Script

**Files:**
- Create: `scripts/deploy.sh`

**Interfaces:**
- Consumes: positional arguments `repository_path`, `wsgi_file`, and the validated 40-character `expected_commit`; an existing `.venv`, `.env`, Git checkout, `~/.my.cnf`, `uv`, `git`, `flock`, `mysqldump`, and `gzip` on PythonAnywhere.
- Produces: a fast-forwarded checkout, five retained compressed database backups under `~/mysql-backups/for-python-anywhere`, applied migrations, collected static files, and a touched WSGI file.

- [ ] **Step 1: Verify the deployment script is absent**

```bash
bash -n scripts/deploy.sh
```

Expected: non-zero exit because `scripts/deploy.sh` does not exist.

- [ ] **Step 2: Add the strict remote deployment script**

Create `scripts/deploy.sh`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

if (( $# != 3 )); then
    echo "Usage: $0 repository_path wsgi_file expected_commit" >&2
    exit 64
fi

repository_path=$1
wsgi_file=$2
expected_commit=$3
backup_dir=$HOME/mysql-backups/for-python-anywhere
lock_file=$HOME/.for-python-anywhere-deploy.lock

if [[ ! "$expected_commit" =~ ^[0-9a-f]{40}$ ]]; then
    echo "expected_commit must be a full 40-character Git SHA." >&2
    exit 64
fi

on_error() {
    local exit_code=$?
    echo "Deployment failed at line ${BASH_LINENO[0]} with exit code ${exit_code}." >&2
    exit "$exit_code"
}
trap on_error ERR

exec 9>"$lock_file"
if ! flock -n 9; then
    echo "Another deployment is already running." >&2
    exit 75
fi

cd "$repository_path"

test -f .env
test -x .venv/bin/python
test -f "$HOME/.my.cnf"
test -f "$wsgi_file"

if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
    echo "Tracked files contain local changes; refusing to deploy." >&2
    exit 65
fi

git fetch --prune origin main
remote_commit=$(git rev-parse origin/main)
if [[ "$remote_commit" != "$expected_commit" ]]; then
    echo "origin/main changed after validation; refusing to deploy." >&2
    exit 65
fi
if ! git merge-base --is-ancestor HEAD "$expected_commit"; then
    echo "The server checkout cannot fast-forward to origin/main." >&2
    exit 65
fi

database_name=$(
    DJANGO_SETTINGS_MODULE=app.settings.production \
        .venv/bin/python -c \
        'from django.conf import settings; print(settings.DATABASES["default"]["NAME"])'
)

mkdir -p "$backup_dir"
backup_file="$backup_dir/$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
mysqldump \
    --defaults-extra-file="$HOME/.my.cnf" \
    --single-transaction \
    --no-tablespaces \
    --routines \
    --triggers \
    "$database_name" | gzip -9 > "$backup_file"

mapfile -t backups < <(
    find "$backup_dir" -type f -name '*.sql.gz' -printf '%T@ %p\n' \
        | sort -nr \
        | cut -d' ' -f2-
)
if (( ${#backups[@]} > 5 )); then
    rm -- "${backups[@]:5}"
fi

git merge --ff-only "$expected_commit"
uv sync --locked --python 3.13
uv run python manage.py check --deploy --settings=app.settings.production
uv run python manage.py migrate --noinput --settings=app.settings.production
uv run python manage.py collectstatic --noinput --clear --settings=app.settings.production
touch "$wsgi_file"

echo "Deployment completed at commit $(git rev-parse --short HEAD)."
```

Make it executable:

```bash
chmod +x scripts/deploy.sh
```

- [ ] **Step 3: Verify syntax and argument failure behavior**

```bash
bash -n scripts/deploy.sh
set +e
output=$(bash scripts/deploy.sh 2>&1)
status=$?
set -e
test "$status" = "64"
test "$output" = "Usage: scripts/deploy.sh repository_path wsgi_file expected_commit"

set +e
output=$(bash scripts/deploy.sh /tmp/repository /tmp/wsgi invalid-sha 2>&1)
status=$?
set -e
test "$status" = "64"
test "$output" = "expected_commit must be a full 40-character Git SHA."
```

Expected: syntax validation exits 0; missing arguments and an invalid commit each exit 64 with the exact validation message.

- [ ] **Step 4: Verify the safety-critical command ordering**

```bash
python - <<'PY'
from pathlib import Path

script = Path("scripts/deploy.sh").read_text()
ordered = [
    "flock -n 9",
    "git fetch --prune origin main",
    '[[ "$remote_commit" != "$expected_commit" ]]',
    "mysqldump",
    'git merge --ff-only "$expected_commit"',
    "uv sync --locked --python 3.13",
    "manage.py check --deploy",
    "manage.py migrate --noinput",
    "manage.py collectstatic --noinput --clear",
    'touch "$wsgi_file"',
]
positions = [script.index(command) for command in ordered]
assert positions == sorted(positions), positions
print("deployment command order passes")
PY
```

Expected: exit 0 and `deployment command order passes`.

- [ ] **Step 5: Commit the deployment script**

```bash
git add scripts/deploy.sh
git commit -m "Add PythonAnywhere deployment script"
```

---

### Task 5: Add the Manually Triggered GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes GitHub secret: `PYTHONANYWHERE_SSH_PRIVATE_KEY`.
- Consumes GitHub variables: `PYTHONANYWHERE_HOST`, `PYTHONANYWHERE_USERNAME`, `PYTHONANYWHERE_KNOWN_HOSTS`, `PYTHONANYWHERE_REPO_PATH`, `PYTHONANYWHERE_WSGI_FILE`, and `PYTHONANYWHERE_DOMAIN`.
- Produces: validation of one captured `main` commit SHA, one serialized SSH deployment of that exact SHA, and a bounded HTTPS health check accepting status 200 through 399.

- [ ] **Step 1: Verify the deployment workflow is absent**

```bash
test -f .github/workflows/deploy.yml
```

Expected: non-zero exit because the workflow does not exist.

- [ ] **Step 2: Add the validation and deployment workflow**

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to PythonAnywhere

on:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: pythonanywhere-production
  cancel-in-progress: false

jobs:
  validate:
    runs-on: ubuntu-latest
    outputs:
      commit: ${{ steps.commit.outputs.sha }}
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_DATABASE: wagtail
          MYSQL_PASSWORD: wagtail
          MYSQL_ROOT_PASSWORD: root-password
          MYSQL_USER: wagtail
        ports:
          - 3306:3306
        options: >-
          --health-cmd="mysqladmin ping -h localhost -u root -proot-password"
          --health-interval=5s
          --health-timeout=5s
          --health-retries=20
    env:
      DJANGO_ALLOWED_HOSTS: localhost,127.0.0.1
      DJANGO_CSRF_TRUSTED_ORIGINS: http://localhost:8000
      DJANGO_DEBUG: "false"
      DJANGO_SECRET_KEY: ci-validation-secret-key-with-at-least-fifty-characters
      MYSQL_DATABASE: wagtail
      MYSQL_HOST: 127.0.0.1
      MYSQL_PASSWORD: wagtail
      MYSQL_PORT: "3306"
      MYSQL_USER: wagtail
      WAGTAILADMIN_BASE_URL: http://localhost:8000
    steps:
      - name: Check out main
        uses: actions/checkout@v4
        with:
          ref: main

      - name: Capture validated commit
        id: commit
        run: echo "sha=$(git rev-parse HEAD)" >> "$GITHUB_OUTPUT"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Set up UV
        uses: astral-sh/setup-uv@v6
        with:
          version: "0.11.28"

      - name: Synchronize dependencies
        run: uv sync --locked --python 3.13

      - name: Run Django checks
        run: uv run python manage.py check --settings=app.settings.production

      - name: Run tests
        run: uv run python manage.py test

      - name: Check migration drift
        run: uv run python manage.py makemigrations --check --dry-run

  deploy:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - name: Configure SSH
        env:
          SSH_PRIVATE_KEY: ${{ secrets.PYTHONANYWHERE_SSH_PRIVATE_KEY }}
          SSH_KNOWN_HOSTS: ${{ vars.PYTHONANYWHERE_KNOWN_HOSTS }}
        run: |
          install -d -m 700 ~/.ssh
          printf '%s\n' "$SSH_PRIVATE_KEY" > ~/.ssh/pythonanywhere
          chmod 600 ~/.ssh/pythonanywhere
          printf '%s\n' "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts
          chmod 600 ~/.ssh/known_hosts

      - name: Deploy origin/main
        env:
          PA_HOST: ${{ vars.PYTHONANYWHERE_HOST }}
          PA_REPO_PATH: ${{ vars.PYTHONANYWHERE_REPO_PATH }}
          PA_USERNAME: ${{ vars.PYTHONANYWHERE_USERNAME }}
          PA_WSGI_FILE: ${{ vars.PYTHONANYWHERE_WSGI_FILE }}
          VALIDATED_COMMIT: ${{ needs.validate.outputs.commit }}
        run: |
          ssh -i ~/.ssh/pythonanywhere \
            -o BatchMode=yes \
            -o StrictHostKeyChecking=yes \
            "$PA_USERNAME@$PA_HOST" \
            "bash '$PA_REPO_PATH/scripts/deploy.sh' '$PA_REPO_PATH' '$PA_WSGI_FILE' '$VALIDATED_COMMIT'"

      - name: Verify the public site
        env:
          PA_DOMAIN: ${{ vars.PYTHONANYWHERE_DOMAIN }}
        run: |
          for attempt in {1..12}; do
            status=$(curl --silent --show-error --output /dev/null \
              --write-out '%{http_code}' "https://$PA_DOMAIN/" || true)
            if [[ "$status" =~ ^[0-9]+$ ]] && (( status >= 200 && status < 400 )); then
              echo "Health check passed with HTTP $status."
              exit 0
            fi
            echo "Attempt $attempt returned HTTP ${status:-none}; retrying."
            sleep 5
          done
          echo "The site did not become healthy after 12 attempts." >&2
          exit 1
```

- [ ] **Step 3: Validate YAML and workflow invariants locally**

```bash
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/deploy.yml"); puts "workflow YAML parses"'
rg -q '^  workflow_dispatch:$' .github/workflows/deploy.yml
! rg -q '^  (push|pull_request):$' .github/workflows/deploy.yml
rg -q 'ref: main' .github/workflows/deploy.yml
rg -q 'needs: validate' .github/workflows/deploy.yml
rg -q 'VALIDATED_COMMIT:.*needs.validate.outputs.commit' .github/workflows/deploy.yml
rg -q 'StrictHostKeyChecking=yes' .github/workflows/deploy.yml
```

Expected: YAML parsing and every invariant assertion exit 0; no automatic push or pull-request trigger exists.

- [ ] **Step 4: Commit the workflow**

```bash
git add .github/workflows/deploy.yml
git commit -m "Add manual PythonAnywhere deployment workflow"
```

---

### Task 6: Document Setup, Operation, and Recovery

**Files:**
- Modify: `README.md`
- Create: `docs/pythonanywhere.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: the exact commands, environment variables, GitHub configuration names, and recovery behavior from Tasks 1-5.
- Produces: a local quick start, an operator runbook sufficient to bootstrap and operate the deployment without reading implementation internals, and accurate repository guidance for future agents.

- [ ] **Step 1: Verify the required documentation headings are absent**

```bash
rg -q '^## Docker Compose development$' README.md
rg -q '^## One-time PythonAnywhere setup$' docs/pythonanywhere.md
```

Expected: non-zero exit because the documentation has not been written.

- [ ] **Step 2: Write the README quick start**

Set `README.md` to:

````markdown
# For PythonAnywhere

A Wagtail site developed with Python 3.13, Django 6, Wagtail 7.4, and MySQL.

## Docker Compose development

Create the ignored local environment file and start the site:

```bash
cp .env.example .env
docker compose up --build
```

Open <http://localhost:8000>. The MySQL database, uploaded media, and collected static files use named Docker volumes.

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

## PythonAnywhere deployment

Production deployment is started manually with **Run workflow** in the GitHub Actions workflow named **Deploy to PythonAnywhere**. The workflow validates `main`, deploys it over SSH, reloads the WSGI app, and verifies the public site.

See [the PythonAnywhere runbook](docs/pythonanywhere.md) for one-time setup, GitHub configuration, deployment operation, and recovery.
````

- [ ] **Step 3: Write the PythonAnywhere operator runbook**

Create `docs/pythonanywhere.md` with these concrete sections and commands:

````markdown
# PythonAnywhere Deployment Runbook

## One-time PythonAnywhere setup

The account must be paid so GitHub Actions can connect over SSH. Confirm the account uses a system image that provides Python 3.13 and confirm UV is available:

```bash
python3.13 --version
uv --version
```

Clone and initialize the application:

```bash
cd "$HOME"
git clone git@github.com:nickmoreton/for-python-anywhere.git
cd "$HOME/for-python-anywhere"
uv sync --locked --python 3.13
cp .env.example .env
chmod 600 .env
```

Edit `.env` on PythonAnywhere. Set `DJANGO_DEBUG=false`, use a new production-only `DJANGO_SECRET_KEY`, set the PythonAnywhere domain in `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, and `WAGTAILADMIN_BASE_URL`, and enter the database name, username, password, hostname, and port shown on PythonAnywhere's Databases page. Do not retain the local example passwords.

Create the permission-restricted MySQL client file used for backups from Django's parsed production settings:

```bash
DJANGO_SETTINGS_MODULE=app.settings.production .venv/bin/python <<'PY'
from pathlib import Path

from django.conf import settings

database = settings.DATABASES["default"]
client_file = Path.home() / ".my.cnf"
client_file.write_text(
    "[client]\n"
    f"user={database['USER']}\n"
    f"password={database['PASSWORD']}\n"
    f"host={database['HOST']}\n"
)
client_file.chmod(0o600)
PY
```

Apply the initial database and static setup:

```bash
uv run python manage.py check --deploy --settings=app.settings.production
uv run python manage.py migrate --noinput --settings=app.settings.production
uv run python manage.py collectstatic --noinput --clear --settings=app.settings.production
uv run python manage.py createsuperuser --settings=app.settings.production
```

Create a manual-configuration PythonAnywhere WSGI web app using Python 3.13. Set its source directory to the output of `echo "$HOME/for-python-anywhere"` and its virtualenv to the output of `echo "$HOME/for-python-anywhere/.venv"`.

Set the PythonAnywhere WSGI file to:

```python
import os
import sys

path = os.path.expanduser("~/for-python-anywhere")
if path not in sys.path:
    sys.path.insert(0, path)

os.environ["DJANGO_SETTINGS_MODULE"] = "app.settings.production"

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
```

In the Web tab, map `/static/` to the output of `echo "$HOME/for-python-anywhere/staticfiles"` and `/media/` to the output of `echo "$HOME/for-python-anywhere/media"`, then reload the web app.

## SSH keys

Create a dedicated deployment key on a trusted local machine:

```bash
ssh-keygen -t ed25519 -f pythonanywhere-deploy -C github-actions-pythonanywhere
```

Append `pythonanywhere-deploy.pub` to `~/.ssh/authorized_keys` on PythonAnywhere. Store the complete contents of `pythonanywhere-deploy` in the GitHub secret `PYTHONANYWHERE_SSH_PRIVATE_KEY`. Never commit either key.

If the repository is private, create a separate key on PythonAnywhere and register its public key as a read-only GitHub deploy key so `git fetch origin main` works without using the Actions deployment key.

## GitHub variables

Configure these GitHub Actions variables:

- `PYTHONANYWHERE_HOST`: `ssh.pythonanywhere.com` for a US account or `ssh.eu.pythonanywhere.com` for an EU account.
- `PYTHONANYWHERE_USERNAME`: the PythonAnywhere account username.
- `PYTHONANYWHERE_REPO_PATH`: the absolute path printed by `echo "$HOME/for-python-anywhere"` on PythonAnywhere.
- `PYTHONANYWHERE_WSGI_FILE`: the absolute WSGI file path shown in the PythonAnywhere Web tab.
- `PYTHONANYWHERE_DOMAIN`: the public domain without `https://` or a trailing slash.
- `PYTHONANYWHERE_KNOWN_HOSTS`: the verified known-hosts line for the selected SSH hostname. Obtain the current host key and verify its fingerprint through a trusted PythonAnywhere source before saving it; do not trust an unverified key captured during a deployment.

## Deploying

Open GitHub Actions, select **Deploy to PythonAnywhere**, choose **Run workflow**, and run it. The workflow always checks out and deploys `main`. A successful run means validation passed, the remote script completed, the WSGI file was touched, and the public HTTPS endpoint returned HTTP 200 through 399.

Overlapping runs are serialized in GitHub and rejected by a server-side lock. The server checkout must contain no tracked local edits and must be able to fast-forward to `origin/main`.

## Failure and recovery

Start with the failed GitHub Actions step. For application startup failures, inspect the error and server logs linked from PythonAnywhere's Web tab. A failure after the checkout updates can expose new files even when workers were not intentionally reloaded, so resolve it promptly.

Database backups are stored in `~/mysql-backups/for-python-anywhere`; the deployment retains the five newest `.sql.gz` files. Do not automatically restore a backup or reverse migrations.

To roll application code back, revert the problematic commit on `main`, push the revert, and run the workflow again. Confirm that the reverted application is compatible with the current database schema before deploying it.

When an explicit database restore is required, disable the web app, identify the intended backup, and run:

```bash
find "$HOME/mysql-backups/for-python-anywhere" -type f -name '*.sql.gz' -print | sort
read -r -p "Enter the exact backup path to restore: " backup_file
test -f "$backup_file"

database_name=$(
  DJANGO_SETTINGS_MODULE=app.settings.production \
    .venv/bin/python -c \
    'from django.conf import settings; print(settings.DATABASES["default"]["NAME"])'
)
gunzip -c "$backup_file" \
  | mysql --defaults-extra-file="$HOME/.my.cnf" "$database_name"
```

Re-enable and reload the web app only after checking migrations and application compatibility.
````

- [ ] **Step 4: Update the repository guide for the new workflow**

In `AGENTS.md`, add these bullets to **Project Structure & Module Organization**:

````markdown
- `compose.yaml` runs the local Wagtail and MySQL services; `.env.example` documents their shared configuration.
- `scripts/start-dev.sh` starts the Compose web service, while `scripts/deploy.sh` performs guarded PythonAnywhere deployments.
- `.github/workflows/deploy.yml` validates and manually deploys `main` to PythonAnywhere.
````

In **Backend Build, Test, and Development**, replace the opening dependency paragraph with:

```markdown
Host development uses UV with Python 3.13. Python dependencies and resolved versions live in `pyproject.toml` and `uv.lock`; the same lockfile is used by Docker, CI, and PythonAnywhere. Host Django commands require a reachable MySQL database configured with the variables documented in `.env.example`. From the repository root:
```

Replace the complete **Container Deployment** section with:

````markdown
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

The Docker image installs dependencies directly from `pyproject.toml` and `uv.lock`; `requirements.txt` is not used.

## PythonAnywhere Deployment

PythonAnywhere runs the project directly from its UV-managed `.venv`; Docker is not used on the host. Production deployment is manually triggered by the `Deploy to PythonAnywhere` GitHub Actions workflow. The workflow validates `main` against MySQL, connects over SSH, runs `scripts/deploy.sh`, reloads the WSGI app, and verifies the public URL. See `docs/pythonanywhere.md` for bootstrap, GitHub variables and secrets, deployment operation, and recovery.
````

- [ ] **Step 5: Verify documentation coverage and commands**

```bash
rg -q '^## Docker Compose development$' README.md
rg -q '^## PythonAnywhere deployment$' README.md
rg -q '^## One-time PythonAnywhere setup$' docs/pythonanywhere.md
rg -q '^## SSH keys$' docs/pythonanywhere.md
rg -q '^## GitHub variables$' docs/pythonanywhere.md
rg -q '^## Deploying$' docs/pythonanywhere.md
rg -q '^## Failure and recovery$' docs/pythonanywhere.md
rg -q 'five newest' docs/pythonanywhere.md
rg -q '^## Docker Compose Development$' AGENTS.md
rg -q '^## PythonAnywhere Deployment$' AGENTS.md
rg -q 'same lockfile is used by Docker, CI, and PythonAnywhere' AGENTS.md
! rg -q 'uses `requirements\.txt`' AGENTS.md
```

Expected: every coverage assertion exits 0.

- [ ] **Step 6: Commit the operator and repository documentation**

```bash
git add README.md docs/pythonanywhere.md AGENTS.md
git commit -m "Document PythonAnywhere deployment operations"
```

---

### Task 7: Run Full Verification

**Files:**
- Review only: all files changed in Tasks 1-6

**Interfaces:**
- Consumes: the complete local, CI, and deployment implementation.
- Produces: fresh evidence that the implementation and updated repository guidance are internally consistent.

- [ ] **Step 1: Run host-side static and Django verification**

```bash
test -f .env || cp .env.example .env
uv sync --locked --python 3.13
uv run python -c "import environ, MySQLdb; print('host dependency imports pass')"
bash -n scripts/start-dev.sh
bash -n scripts/deploy.sh
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/deploy.yml")'
git diff --check
```

Expected: all commands exit 0, dependency imports pass, both shell scripts parse, the workflow YAML parses, and the diff has no whitespace errors. Database-backed checks run in the next step against Compose MySQL.

- [ ] **Step 2: Run the complete test suite against Compose MySQL**

```bash
docker compose up -d db
docker compose run --rm web python manage.py test
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose down
```

Expected: all Django tests pass, system checks report no issues, and no migrations are generated.

- [ ] **Step 3: Build and smoke-test the local application**

```bash
docker compose build web
docker compose up -d
curl --fail --retry 10 --retry-delay 2 http://localhost:8000/
docker compose down
```

Expected: the image builds and the homepage returns an HTTP success response.

- [ ] **Step 4: Review the final diff and commit any verification-only corrections**

```bash
git status --short
git diff --check
git log --oneline -7
```

Expected: no unintended files or secrets are tracked. If verification required a correction, stage only the affected implementation files and commit them with a message describing that correction; otherwise make no empty commit.

- [ ] **Step 5: Verify the repository guide matches the implemented workflow**

```bash
rg -q 'Python 3.13' AGENTS.md
rg -q 'docker compose up --build' AGENTS.md
rg -q 'Deploy to PythonAnywhere' AGENTS.md
! rg -q 'Python 3.14|Python 3.12|requirements\.txt.*container environment|SQLite' AGENTS.md
```

Expected: every assertion exits 0, confirming that the authorized `AGENTS.md` update no longer describes the superseded runtime, dependency, or database workflow.
