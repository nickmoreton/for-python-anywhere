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
