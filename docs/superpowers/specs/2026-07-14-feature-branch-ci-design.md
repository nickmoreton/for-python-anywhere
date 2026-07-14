# Feature Branch CI Design

## Goal

Validate the Django/Wagtail application whenever a commit is pushed to any
branch other than `main`. Feature work should receive the same application
checks used before a production deployment, without making branch pushes able
to trigger deployment.

## Scope

Add a dedicated GitHub Actions workflow at `.github/workflows/ci.yml`. The
workflow will run for pushes to every branch except `main`. Pull-request events,
automatic deployment, dependency caching, test coverage, linting, and type
checking are outside this change.

The existing manually triggered `.github/workflows/deploy.yml` remains
unchanged. Keeping validation and deployment in separate workflows makes their
permissions and triggers easy to audit.

## Workflow Design

The workflow will have read-only repository permissions and one validation job
on `ubuntu-latest`. It will check out the pushed commit, run Python 3.13, and use
UV 0.11.28 so its runtime and dependency installation match the current Docker
and deployment configuration.

A MySQL 8.0 service will use the same CI credentials and health check as the
deployment workflow. The job will provide the production-like Django and MySQL
environment variables already used during deployment validation.

After checkout and environment setup, the job will:

1. Install the locked dependency set with `uv sync --locked --python 3.13`.
2. Run `python manage.py check` with `app.settings.production`.
3. Grant the application user access to Django's `test_wagtail` database.
4. Run the Django test suite.
5. Run `makemigrations --check --dry-run` to detect migration drift.

GitHub Actions concurrency will group runs by workflow and branch ref. A newer
push to the same branch will cancel an older in-progress run, while pushes to
different branches can validate independently.

## Failure Behavior

Any failed setup or validation step will fail the workflow and prevent a green
branch status. MySQL readiness is enforced by the service health check. The
workflow will not retry application checks or mutate external systems.

## Verification

The implementation will be verified by:

- Parsing the new workflow as YAML.
- Asserting that its push trigger excludes `main`.
- Confirming the validation commands and environment match the repository's
  supported Python, UV, MySQL, Django check, test, and migration-drift setup.
- Running the repository's Django checks, tests, and migration-drift command
  against MySQL when the local environment provides a reachable test database.

## Documentation Impact

The repository structure and supported workflow list change, so `AGENTS.md`
should eventually mention feature-branch CI. This task will not edit
`AGENTS.md`, because its repository instructions only authorize a reminder
unless that file is explicitly included in the requested scope.
