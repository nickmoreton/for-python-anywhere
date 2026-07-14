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

Edit `.env` on PythonAnywhere. Set `DJANGO_DEBUG=false`, use a new production-only `DJANGO_SECRET_KEY`, set the PythonAnywhere domain in `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, and `WAGTAILADMIN_BASE_URL`, and enter the database name, username, password, hostname, and port shown on PythonAnywhere's Databases page. Do not retain the local example passwords. `MYSQL_ROOT_PASSWORD` is used only by the local Compose database and is not required by the production Django application.

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
- `PYTHONANYWHERE_KNOWN_HOSTS`: the verified known-hosts line for the selected SSH hostname. Obtain the current host key and verify its fingerprint through a trusted PythonAnywhere source before saving it; do not trust an unverified key captured during a deployment. The workflow writes this value to `~/.ssh/known_hosts` and connects with `StrictHostKeyChecking=yes`.

## Deploying

Open GitHub Actions, select **Deploy to PythonAnywhere**, choose **Run workflow**, and run it. The workflow always checks out and validates `main`, captures its full 40-character commit SHA, and requires the server's `origin/main` to still match that exact SHA before deploying it. A successful run means validation passed, the remote script completed, the WSGI file was touched, and the public HTTPS endpoint returned HTTP 200 through 399.

Overlapping runs are serialized in GitHub and rejected by a server-side lock. The server checkout must contain no tracked local edits and must be able to fast-forward to the validated commit on `origin/main`.

## Failure and recovery

Start with the failed GitHub Actions step. For application startup failures, inspect the error and server logs linked from PythonAnywhere's Web tab. A failure after the checkout updates can expose new files even when workers were not intentionally reloaded, so resolve it promptly.

Database backups are stored in `~/mysql-backups/for-python-anywhere`; each deployment creates a compressed backup before changing the checkout and retains the five newest `.sql.gz` files. Do not automatically restore a backup or reverse migrations.

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
