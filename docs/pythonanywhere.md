# PythonAnywhere Deployment Runbook

## One-time PythonAnywhere setup

The account must be paid so GitHub Actions can connect over SSH. Confirm the account uses a system image that provides Python 3.13 and confirm UV is available:

```bash
python3.13 --version
uv --version
```

Install NVM in the path used by the noninteractive deployment script. Skip the clone command when `$HOME/nvm/nvm.sh` already exists:

```bash
git clone --depth 1 https://github.com/nvm-sh/nvm.git "$HOME/nvm"
export NVM_DIR="$HOME/nvm"
source "$NVM_DIR/nvm.sh"
```

Before cloning a private repository, create a repository-only SSH key on PythonAnywhere with an empty passphrase:

```bash
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
ssh-keygen -t ed25519 -N '' -f "$HOME/.ssh/github-repository" -C pythonanywhere-read-only
cat "$HOME/.ssh/github-repository.pub"
```

In the GitHub repository, open **Settings > Deploy keys**, add the displayed public key, and leave **Allow write access** disabled. This key is only for PythonAnywhere to read the private repository; it is separate from the key GitHub Actions uses to connect to PythonAnywhere.

Capture GitHub's current host keys, inspect their fingerprints, and compare them with fingerprints published by GitHub through a separate trusted connection before installing them. Do not trust keys merely because `ssh-keyscan` returned them:

```bash
ssh-keyscan -t ed25519 github.com > "$HOME/.ssh/github.com.candidate"
ssh-keygen -lf "$HOME/.ssh/github.com.candidate"
# Stop here until every candidate fingerprint has been verified against GitHub's documentation.
cat "$HOME/.ssh/github.com.candidate" >> "$HOME/.ssh/known_hosts"
rm "$HOME/.ssh/github.com.candidate"
chmod 600 "$HOME/.ssh/known_hosts"
```

Configure SSH to use only the read-only repository key for GitHub:

```bash
cat >> "$HOME/.ssh/config" <<'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github-repository
    IdentitiesOnly yes
    StrictHostKeyChecking yes
EOF
chmod 600 "$HOME/.ssh/config"
```

Test the connection:

```bash
ssh -T git@github.com
```

The expected result is a GitHub authentication message that identifies the repository deploy key and states that shell access is unavailable; the command returns status 1 because GitHub does not provide shell access. Then clone and initialize the private repository:

```bash
cd "$HOME"
git clone git@github.com:nickmoreton/for-python-anywhere.git
cd "$HOME/for-python-anywhere"
uv sync --locked --python 3.13
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

For a public repository, no GitHub deploy key is needed: use `git clone https://github.com/nickmoreton/for-python-anywhere.git` instead. The trusted-host and SSH configuration above are required for the private-repository SSH path.

Before configuring `.env` or running migrations, open PythonAnywhere's **Databases** tab. Initialize the account's MySQL password if it has not been set, then create the production MySQL database. Record the database name, username, password, hostname, and port displayed there; creating the database and setting the password are one-time control-panel operations.

Create the restricted production environment file only after the database exists:

```bash
cd "$HOME/for-python-anywhere"
cp .env.example .env
chmod 600 .env
```

Edit `.env` on PythonAnywhere. Set `DJANGO_DEBUG=false`, use a new production-only `DJANGO_SECRET_KEY`, set the PythonAnywhere domain in `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, and `WAGTAILADMIN_BASE_URL`, and enter the recorded production database values. Do not retain the local example passwords. `MYSQL_ROOT_PASSWORD` is used only by the local Compose database and is not required by the production Django application.

In a PythonAnywhere Bash console, after configuring `.env` and creating `.venv`, run the following from the repository root. It creates the permission-restricted `~/.my.cnf` file used by backup and restore commands, using the production database credentials loaded by Django:

```bash
cd "$HOME/for-python-anywhere"
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
    f"port={database['PORT']}\n"
)
client_file.chmod(0o600)
PY
```

Apply the initial database and static setup:

```bash
uv run python manage.py check --deploy --settings=app.settings.production
uv run python manage.py migrate --noinput --settings=app.settings.production
npm ci
npm run build
uv run python manage.py collectstatic --noinput --clear --settings=app.settings.production
rm -rf -- node_modules
uv run python manage.py createsuperuser --settings=app.settings.production
```

The final cleanup removes build-only Node dependencies after static files have been collected. If an earlier command fails, `node_modules` remains available for diagnosis; rerun `npm ci` before retrying the build.

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

Create a dedicated deployment key on a trusted local machine. The empty passphrase is deliberate: the noninteractive GitHub Actions job cannot answer a passphrase prompt, and this key must be dedicated to this one deployment connection:

```bash
ssh-keygen -t ed25519 -N '' -f pythonanywhere-deploy -C github-actions-pythonanywhere
```

On PythonAnywhere, create the SSH directory and authorized-keys file with restricted permissions, then append the complete single line from `pythonanywhere-deploy.pub`:

```bash
install -d -m 700 "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
chmod 600 "$HOME/.ssh/authorized_keys"
printf '%s\n' 'paste the complete pythonanywhere-deploy.pub line here' >> "$HOME/.ssh/authorized_keys"
```

In the GitHub repository, open **Settings > Secrets and variables > Actions**. On the **Secrets** tab, under **Repository secrets**, select **New repository secret** and store the complete contents of `pythonanywhere-deploy` as `PYTHONANYWHERE_SSH_PRIVATE_KEY`. Never commit either key. Keep the local files until the public key has been added to PythonAnywhere, the private key has been saved in GitHub, and a deployment has succeeded. You may then remove the local copies from the trusted machine:

```bash
rm -- pythonanywhere-deploy pythonanywhere-deploy.pub
```

Deleting these local files does not revoke the deployment key: GitHub retains the private key in the Actions secret and PythonAnywhere retains the public key in `~/.ssh/authorized_keys`. If the GitHub secret must be recreated later, generate and install a new key pair. This dedicated key authorizes a normal PythonAnywhere shell login; it is not restricted to the deployment script. Protect the GitHub secret accordingly, remove the matching `authorized_keys` line immediately if exposure is suspected, and generate and install a replacement key. A forced-command wrapper is not documented because it would need to parse and validate the workflow's path arguments and exact-SHA argument, adding a second brittle deployment interface.

For a private repository, the separate read-only GitHub deploy key configured during one-time setup lets `git fetch origin main` work without reusing this Actions deployment key.

## GitHub variables

In the GitHub repository, open **Settings > Secrets and variables > Actions**, then select the **Variables** tab. Under **Repository variables**, select **New repository variable** and add each variable below separately. Do not add them under **Settings > Environments**: the deployment workflow does not declare a GitHub environment, so environment-level variables are not available to it.

- `PYTHONANYWHERE_HOST`: `ssh.pythonanywhere.com` for a US account or `ssh.eu.pythonanywhere.com` for an EU account.
- `PYTHONANYWHERE_USERNAME`: the PythonAnywhere account username.
- `PYTHONANYWHERE_REPO_PATH`: the absolute path printed by `echo "$HOME/for-python-anywhere"` on PythonAnywhere.
- `PYTHONANYWHERE_WSGI_FILE`: the absolute WSGI file path shown in the PythonAnywhere Web tab.
- `PYTHONANYWHERE_DOMAIN`: the public domain without `https://` or a trailing slash.
- `PYTHONANYWHERE_KNOWN_HOSTS`: the complete, verified SSH host-key line obtained using the procedure below. This is not the shorter SHA-256 fingerprint.

On a trusted local machine, set `host` to the same hostname used for `PYTHONANYWHERE_HOST`, then capture the current RSA host key in a temporary file:

```bash
# Use ssh.pythonanywhere.com for a US account.
host=ssh.eu.pythonanywhere.com
candidate_file=$(mktemp)
ssh-keyscan -T 10 -t rsa "$host" 2>/dev/null \
  | awk '!/^#/ && NF' \
  | sort -u > "$candidate_file"
```

Display the captured key's SHA-256 fingerprint:

```bash
ssh-keygen -lf "$candidate_file" -E sha256
```

Compare that fingerprint with the one published on PythonAnywhere's official [SSH Access](https://help.pythonanywhere.com/pages/SSHAccess) page, reached through a separate trusted browser connection. Stop if they do not match. `ssh-keyscan` retrieves a key but does not prove that it is authentic; the comparison provides that verification.

After the fingerprint matches, display the complete host-key line:

```bash
cat "$candidate_file"
```

Copy the entire line, beginning with the selected SSH hostname, into the GitHub Actions variable `PYTHONANYWHERE_KNOWN_HOSTS`; do not copy only the fingerprint. Then remove the temporary file:

```bash
rm -f "$candidate_file"
```

The deployment workflow writes this value to `~/.ssh/known_hosts` and connects with `StrictHostKeyChecking=yes`.

## Deploying

Open GitHub Actions, select **Deploy to PythonAnywhere**, choose **Run workflow**, and run it. The workflow always checks out and validates `main`, captures its full 40-character commit SHA, and requires the server's `origin/main` to still match that exact SHA before deploying it. A successful run means validation passed, the remote script completed, the WSGI file was touched, and the public HTTPS endpoint returned HTTP 200 through 399.

Overlapping runs are serialized in GitHub and rejected by a server-side lock. The server checkout must contain no tracked local edits and must be able to fast-forward to the validated commit on `origin/main`.

## Failure and recovery

Start with the failed GitHub Actions step. For application startup failures, inspect the error and server logs linked from PythonAnywhere's Web tab. A failure after the checkout updates can expose new files even when workers were not intentionally reloaded, so resolve it promptly.

Database backups are stored in `~/mysql-backups/for-python-anywhere`; each deployment creates a compressed backup before changing the checkout and retains the five newest `.sql.gz` files. Do not automatically restore a backup or reverse migrations.

To roll application code back, revert the problematic commit on `main`, push the revert, and run the workflow again. Confirm that the reverted application is compatible with the current database schema before deploying it.

When an operator has explicitly decided that a database restore is required, disable the web app, identify the intended backup, and run this from the application checkout. The script accepts only an existing file from the application's backup directory, validates the gzip stream before invoking MySQL, and terminates on a missing or invalid selection:

```bash
set -euo pipefail

lock_file=$HOME/.for-python-anywhere-deploy.lock
exec 9>"$lock_file"
if ! flock -n 9; then
  echo "A deployment or database restore is already running; restore aborted." >&2
  exit 75
fi

cd "$HOME/for-python-anywhere"
backup_dir="$HOME/mysql-backups/for-python-anywhere"
find "$backup_dir" -maxdepth 1 -type f -name '*.sql.gz' -print | sort
read -r -p "Enter the exact backup path to restore: " backup_file

case "$backup_file" in
  "$backup_dir"/*.sql.gz)
    backup_name=${backup_file#"$backup_dir"/}
    ;;
  *)
    echo "Backup must be a .sql.gz file in $backup_dir" >&2
    exit 1
    ;;
esac

if [[ -z "$backup_name" || "$backup_name" == */* || ! -f "$backup_file" || -L "$backup_file" ]]; then
  echo "Backup selection is missing or invalid" >&2
  exit 1
fi

gzip -t "$backup_file"

database_name=$(
  DJANGO_SETTINGS_MODULE=app.settings.production \
    .venv/bin/python -c \
    'from django.conf import settings; print(settings.DATABASES["default"]["NAME"])'
)
gunzip -c "$backup_file" \
  | mysql --defaults-extra-file="$HOME/.my.cnf" "$database_name"

uv run python manage.py check --deploy --settings=app.settings.production
uv run python manage.py migrate --plan --settings=app.settings.production
flock -u 9
```

Review the migration plan and confirm application compatibility with the restored schema before re-enabling and reloading the web app. The restore holds the same nonblocking lock as `scripts/deploy.sh` through both documented compatibility checks, so a deployment cannot start during the destructive operation.
