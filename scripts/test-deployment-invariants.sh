#!/usr/bin/env bash
set -Eeuo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

assert_dockerignore_entry() {
    local entry=$1
    grep -Fxq "$entry" .dockerignore || fail ".dockerignore is missing $entry"
}

assert_dockerignore_entry '.worktrees/'
assert_dockerignore_entry '.superpowers/'

rg -q 'date -u \+%Y%m%dT%H%M%S%NZ.*\$\$' scripts/deploy.sh \
    || fail "backup final names do not include subsecond time and process identity"
rg -q '^ln -- "\$backup_temp" "\$backup_file"$' scripts/deploy.sh \
    || fail "backup publication is not atomic and no-clobber"
rg -q 'find "\$backup_dir" -maxdepth 1 -type f' scripts/deploy.sh \
    || fail "backup retention is not limited to the flat backup directory"

rg -q "printf -v remote_command .*%q" .github/workflows/deploy.yml \
    || fail "workflow does not construct the remote command with shell escaping"
rg -q 'ssh .*|"\$remote_command"' .github/workflows/deploy.yml \
    || fail "workflow does not pass the escaped remote command to SSH"
! rg -q '"bash '\''\$PA_REPO_PATH' .github/workflows/deploy.yml \
    || fail "workflow still interpolates configured paths inside single quotes"

restore_block=$(sed -n '/^```bash$/,/^```$/p' docs/pythonanywhere.md | tail -n 55)
grep -Fq 'lock_file=$HOME/.for-python-anywhere-deploy.lock' <<< "$restore_block" \
    || fail "restore does not use the deployment lock path"
grep -Fq 'flock -n 9' <<< "$restore_block" \
    || fail "restore does not acquire the deployment lock nonblockingly"
grep -Fq 'flock -u 9' <<< "$restore_block" \
    || fail "restore does not release the lock after compatibility checks"

rg -q 'chmod 700 "?\$HOME/\.ssh"?' docs/pythonanywhere.md \
    || fail "runbook does not set ~/.ssh to 0700"
rg -q 'chmod 600 "?\$HOME/\.ssh/authorized_keys"?' docs/pythonanywhere.md \
    || fail "runbook does not set authorized_keys to 0600"

rg -q '^export NVM_DIR="\$HOME/nvm"$' scripts/deploy.sh \
    || fail "deployment does not use the confirmed NVM directory"
rg -q '^source "\$NVM_DIR/nvm\.sh"$' scripts/deploy.sh \
    || fail "deployment does not source NVM"
rg -q '^nvm install$' scripts/deploy.sh \
    || fail "deployment does not install the pinned Node version"
! rg -q '^nvm use$' scripts/deploy.sh \
    || fail "deployment still requires the pinned Node version to be preinstalled"

deploy_nvm_line=$(rg -n '^source "\$NVM_DIR/nvm\.sh"$' scripts/deploy.sh | cut -d: -f1)
deploy_nvm_install_line=$(rg -n '^nvm install$' scripts/deploy.sh | cut -d: -f1)
deploy_ci_line=$(rg -n '^npm ci$' scripts/deploy.sh | cut -d: -f1)
deploy_build_line=$(rg -n '^npm run build$' scripts/deploy.sh | cut -d: -f1)
deploy_migrate_line=$(rg -n '^uv run python manage\.py migrate ' scripts/deploy.sh | cut -d: -f1)
deploy_collectstatic_line=$(rg -n '^uv run python manage\.py collectstatic ' scripts/deploy.sh | cut -d: -f1)
deploy_reload_line=$(rg -n '^touch "\$wsgi_file"$' scripts/deploy.sh | cut -d: -f1)

(( deploy_nvm_line < deploy_nvm_install_line \
    && deploy_nvm_install_line < deploy_ci_line \
    && deploy_ci_line < deploy_build_line \
    && deploy_build_line < deploy_migrate_line \
    && deploy_build_line < deploy_collectstatic_line \
    && deploy_build_line < deploy_reload_line )) \
    || fail "frontend build is not ordered before Django mutation and reload"

rg -q 'git clone --depth 1 https://github\.com/nvm-sh/nvm\.git "\$HOME/nvm"' docs/pythonanywhere.md \
    || fail "runbook does not document NVM installation"
rg -Fq 'automatically installs and activates the exact Node.js version pinned in `.nvmrc`' docs/pythonanywhere.md \
    || fail "runbook does not document automatic pinned Node installation"
rg -q '^nvm install$' docs/pythonanywhere.md \
    || fail "runbook does not install the .nvmrc version"
rg -q '^npm ci$' docs/pythonanywhere.md \
    || fail "runbook does not install locked frontend dependencies"
rg -q '^npm run build$' docs/pythonanywhere.md \
    || fail "runbook does not build initial frontend assets"

echo "PASS: deployment static invariants"
