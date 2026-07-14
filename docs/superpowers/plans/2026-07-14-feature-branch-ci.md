# Feature Branch CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GitHub Actions validation for every pushed branch except `main` without changing the manual production deployment workflow.

**Architecture:** Create one dedicated `.github/workflows/ci.yml` workflow with a non-`main` push trigger, branch-scoped concurrency, and a single MySQL-backed validation job. Mirror the runtime, environment, and validation commands already proven in `.github/workflows/deploy.yml`, while checking out the pushed commit and omitting every deployment step.

**Tech Stack:** GitHub Actions, Ubuntu, Python 3.13, UV 0.11.28, Django/Wagtail, MySQL 8.0, PyYAML for local structural verification.

## Global Constraints

- Run on pushes to every branch except `main`; do not add a pull-request trigger.
- Keep `.github/workflows/deploy.yml` unchanged and manually triggered.
- Use read-only `contents` permission.
- Use Python `3.13`, UV `0.11.28`, and MySQL `8.0`.
- Run the production settings check, Django test suite, and migration-drift check.
- Cancel an older in-progress run when a newer commit is pushed to the same branch.
- Do not add dependency caching, coverage, linting, type checking, or external mutations.

---

## File Structure

- Create `.github/workflows/ci.yml`: owns feature-branch push triggers, concurrency, the MySQL service, CI environment, dependency setup, and Django validation steps.
- Do not modify `.github/workflows/deploy.yml`: production validation and deployment remain isolated behind `workflow_dispatch`.
- Do not modify `AGENTS.md`: remind the user at handoff that its workflow inventory should be updated separately, as required by the repository instructions.

### Task 1: Add the Feature Branch Validation Workflow

**Files:**
- Create: `.github/workflows/ci.yml`
- Verify: `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes: `pyproject.toml`, `uv.lock`, `manage.py`, `app.settings.production`, and the MySQL environment-variable contract already used by `.github/workflows/deploy.yml`.
- Produces: a GitHub Actions workflow named `Feature Branch CI` that validates the pushed commit for all branches except `main`.

- [ ] **Step 1: Run a structural test that fails because the workflow is absent**

Run:

```bash
uv run --with pyyaml python - <<'PY'
from pathlib import Path
import yaml

workflow_path = Path(".github/workflows/ci.yml")
assert workflow_path.is_file(), f"missing {workflow_path}"

workflow = yaml.load(workflow_path.read_text(), Loader=yaml.BaseLoader)
assert workflow["name"] == "Feature Branch CI"
assert workflow["on"] == {"push": {"branches-ignore": ["main"]}}
assert workflow["permissions"] == {"contents": "read"}
assert workflow["concurrency"] == {
    "group": "${{ github.workflow }}-${{ github.ref }}",
    "cancel-in-progress": "true",
}

validate = workflow["jobs"]["validate"]
assert validate["runs-on"] == "ubuntu-latest"
assert validate["services"]["mysql"]["image"] == "mysql:8.0"

steps = validate["steps"]
assert steps[0] == {"name": "Check out pushed commit", "uses": "actions/checkout@v4"}
assert any(step.get("uses") == "actions/setup-python@v5" for step in steps)
assert any(step.get("uses") == "astral-sh/setup-uv@v6" for step in steps)

runs = [step.get("run", "") for step in steps]
assert "uv sync --locked --python 3.13" in runs
assert "uv run python manage.py check --settings=app.settings.production" in runs
assert "uv run python manage.py test" in runs
assert "uv run python manage.py makemigrations --check --dry-run" in runs
PY
```

Expected: FAIL with `AssertionError: missing .github/workflows/ci.yml`.

- [ ] **Step 2: Create the minimal workflow**

Create `.github/workflows/ci.yml` with exactly:

```yaml
name: Feature Branch CI

on:
  push:
    branches-ignore:
      - main

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  validate:
    runs-on: ubuntu-latest
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
      - name: Check out pushed commit
        uses: actions/checkout@v4

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

      - name: Grant test database privileges
        env:
          MYSQL_ROOT_PASSWORD: root-password
        run: |
          docker exec --env MYSQL_PWD="$MYSQL_ROOT_PASSWORD" \
            "${{ job.services.mysql.id }}" \
            mysql --user=root \
            --execute="GRANT ALL PRIVILEGES ON \`test_wagtail\`.* TO 'wagtail'@'%';"

      - name: Run tests
        run: uv run python manage.py test

      - name: Check migration drift
        run: uv run python manage.py makemigrations --check --dry-run
```

- [ ] **Step 3: Re-run the structural test and verify it passes**

Run the complete PyYAML command from Step 1 again.

Expected: exit status 0 with no assertion output.

- [ ] **Step 4: Verify the deployment workflow is unchanged**

Run:

```bash
git diff --exit-code HEAD -- .github/workflows/deploy.yml
```

Expected: exit status 0 with no output.

- [ ] **Step 5: Run repository whitespace validation**

Run:

```bash
git diff --check
```

Expected: exit status 0 with no output.

- [ ] **Step 6: Run application validation when MySQL is available**

If Docker is available, run the repository-supported Compose commands:

```bash
docker compose run --rm web python manage.py check --settings=app.settings.production
docker compose run --rm web python manage.py test
docker compose run --rm web python manage.py makemigrations --check --dry-run
```

Expected: each command exits 0; the test command reports all tests passing and the migration command reports `No changes detected`.

If Docker or its daemon is unavailable, report that limitation explicitly; do not replace these commands with an invented validation command.

- [ ] **Step 7: Review the final diff against the design**

Run:

```bash
git diff -- .github/workflows/ci.yml
git status --short
```

Expected: the only uncommitted implementation file is `.github/workflows/ci.yml`; the workflow contains the approved trigger, concurrency behavior, MySQL-backed validation, and no deployment steps.

- [ ] **Step 8: Commit the workflow**

```bash
git add .github/workflows/ci.yml
git commit -m "Add feature branch CI workflow"
```
