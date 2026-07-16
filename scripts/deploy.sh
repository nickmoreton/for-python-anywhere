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

tracked_changes=$(git status --porcelain --untracked-files=no)
if [[ -n "$tracked_changes" ]]; then
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
backup_temp=$(mktemp "$backup_dir/.backup.XXXXXXXXXX.tmp")
backup_file="$backup_dir/$(date -u +%Y%m%dT%H%M%S%NZ)-$$.sql.gz"
cleanup_backup() {
    rm -f -- "$backup_temp"
}
trap cleanup_backup EXIT
mysqldump \
    --defaults-extra-file="$HOME/.my.cnf" \
    --single-transaction \
    --no-tablespaces \
    --routines \
    --triggers \
    "$database_name" | gzip -9 > "$backup_temp"
ln -- "$backup_temp" "$backup_file"
rm -- "$backup_temp"
trap - EXIT

backup_list=$(
    find "$backup_dir" -maxdepth 1 -type f -name '*.sql.gz' -printf '%T@ %p\n' \
        | sort -nr \
        | cut -d' ' -f2-
)
backups=()
if [[ -n "$backup_list" ]]; then
    while IFS= read -r backup; do
        backups+=("$backup")
    done <<< "$backup_list"
fi
if (( ${#backups[@]} > 5 )); then
    rm -- "${backups[@]:5}"
fi

git merge --ff-only "$expected_commit"
uv sync --locked --python 3.13
export NVM_DIR="$HOME/nvm"
source "$NVM_DIR/nvm.sh"
nvm install
npm ci
npm run build
uv run python manage.py check --deploy --settings=app.settings.production
uv run python manage.py migrate --noinput --settings=app.settings.production
uv run python manage.py collectstatic --noinput --clear --settings=app.settings.production
rm -rf -- node_modules
touch "$wsgi_file"

echo "Deployment completed at commit $(git rev-parse --short HEAD)."
