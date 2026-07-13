# PythonAnywhere Deployment Automation Design

## Goal

Provide a manually triggered GitHub Actions deployment for the Wagtail site on a paid PythonAnywhere account. Local development will use Docker Compose, while PythonAnywhere will run the application directly from a Python 3.13 virtual environment managed by UV.

The local, CI, and production environments will share Python 3.13, one `pyproject.toml`/`uv.lock` dependency source, MySQL, the same settings contract, and the same migration and static-file commands. Docker remains a local-development tool and is not used on PythonAnywhere.

## Scope

This work includes:

- Standardizing the repository, Docker image, CI, and PythonAnywhere on Python 3.13.
- Adding MySQL as the development, CI, and production database.
- Adding Docker Compose for local development.
- Defining a common environment-variable contract.
- Adding a manually triggered GitHub Actions deployment workflow.
- Adding a repository-owned remote deployment script.
- Documenting the one-time PythonAnywhere setup and recovery procedure.

It does not include provisioning the PythonAnywhere account, web app, MySQL database, DNS, or TLS through automation. Those remain one-time manual operations.

## Architecture

### Local development

Docker Compose runs two services:

- `web`: the Django/Wagtail application built with Python 3.13 from the repository Dockerfile.
- `db`: MySQL with a persistent named volume and a health check.

The web service bind-mounts the source tree for development and uses persistent media storage. It waits for MySQL to become healthy, applies migrations, collects static files, and starts the Django development server. Local developers copy `.env.example` to the ignored `.env` file before starting Compose.

The Docker image installs UV from its official container image and runs `uv sync --locked` against the repository's `pyproject.toml` and `uv.lock`. The redundant `requirements.txt` file is removed so local Docker, host development, CI, and PythonAnywhere cannot drift between dependency sources.

### GitHub Actions

The deployment workflow uses only `workflow_dispatch`; pushes do not deploy automatically. Clicking **Run workflow** is the sole approval gate, after which validation and deployment proceed without a second manual approval.

The workflow explicitly checks out and deploys `origin/main`, regardless of which GitHub UI ref was used to start the workflow. It first validates that exact revision on Python 3.13 with a MySQL service:

1. Install dependencies with `uv sync --locked`.
2. Run Django system checks.
3. Run the Django test suite.
4. Run `makemigrations --check --dry-run`.

If validation succeeds, the runner passes the validated commit SHA to PythonAnywhere over OpenSSH and invokes the repository-owned deployment script. The script refuses to deploy if `origin/main` no longer equals that SHA, ensuring that the tested revision is the deployed revision. The workflow avoids a third-party SSH action.

### PythonAnywhere

PythonAnywhere holds:

- A checkout at `/home/${PYTHONANYWHERE_USERNAME}/for-python-anywhere` tracking `origin/main`.
- A Python 3.13 project virtual environment at `.venv`, managed by UV.
- An ignored production `.env` file.
- A manually configured WSGI web app that uses `app.settings.production` and the project virtual environment.
- Static and media URL mappings configured in the Web tab.
- A MySQL database and restricted MySQL backup credentials.
- The GitHub Actions deployment public key in `~/.ssh/authorized_keys`.
- For a private repository, a separate read-only GitHub deploy key used by the server checkout.

The GitHub Actions SSH private key is stored as a repository or GitHub environment secret. The PythonAnywhere SSH host, username, application domain, checkout path, and WSGI file path are configuration variables rather than secrets.

## Configuration Contract

Django settings use `django-environ` to load configuration from environment variables and an ignored `.env` file. `.env.example` documents every required variable with safe development defaults and clearly marked example values for secrets.

The contract covers at least:

- Django secret key.
- Debug mode.
- Allowed hosts and CSRF trusted origins.
- MySQL database name, user, password, host, and port.
- Wagtail administrator base URL.

Local Compose and PythonAnywhere use the same variable names with environment-specific values. Production secrets are never committed. Management commands explicitly use `app.settings.production` during deployment.

## Deployment Flow

The remote script uses strict shell error handling and performs these steps:

1. Acquire a non-blocking deployment lock so overlapping runs cannot modify the checkout or database.
2. Change to the configured repository directory.
3. Verify that required production configuration is present and that the checkout has no unexpected tracked changes.
4. Fetch `origin/main`, verify that it still equals the commit validated by GitHub Actions, and verify that the current checkout can be fast-forwarded.
5. Create a timestamped MySQL dump and retain the five most recent deployment backups.
6. Fast-forward the checkout to `origin/main` without merges or destructive resets.
7. Run `uv sync --locked` with Python 3.13.
8. Run Django's production deployment checks.
9. Apply migrations with `--noinput`.
10. Collect static files with `--noinput --clear`.
11. Touch the configured PythonAnywhere WSGI file to reload the web workers.

After the SSH command succeeds, GitHub Actions polls the application's public HTTPS URL with bounded retries. The workflow succeeds only when the application returns an HTTP status from 200 through 399.

## Failure and Recovery

Any failed command terminates the deployment and makes the GitHub Actions run fail visibly. A failure before the WSGI reload does not intentionally restart the existing workers, although an in-place checkout can expose updated templates or other files before reload; the recovery guide will therefore treat any post-checkout failure as requiring operator attention. The fast-forward-only Git policy prevents accidental merge commits or forced replacement of server state.

The database is backed up before migrations. The deployment does not automatically restore that backup or reverse migrations: data-changing and non-transactional migrations require operator judgment. Recovery instructions will identify the failed revision, application and PythonAnywhere logs, available database backup, and explicit restore procedure.

If the post-reload health check fails, the workflow reports failure and directs the operator to PythonAnywhere's error and server logs. Application code rollback and database recovery remain explicit actions because their safe ordering depends on the migration involved.

## Verification

Implementation is complete when all of the following pass:

- UV resolves and locks the Python 3.13 dependency set.
- `python manage.py check` passes.
- `python manage.py test` passes.
- `python manage.py makemigrations --check --dry-run` reports no drift.
- Docker Compose configuration validates and its images build.
- The Compose MySQL service becomes healthy and Django checks/tests pass against it.
- The workflow YAML is syntactically valid and is restricted to manual dispatch.
- The deployment script passes a shell syntax check and its failure paths are tested where practical without contacting production.
- A documented first deployment completes on PythonAnywhere and its public health check passes.

## Documentation Impact

The implementation changes the documented Python version, dependency handling, local startup commands, database configuration, and deployment workflow. `README.md` will document developer setup and deployment operation. The user explicitly authorized updating `AGENTS.md` in the same change so the repository guide describes UV as the single dependency source, Docker Compose development, and the GitHub Actions/PythonAnywhere workflow.
