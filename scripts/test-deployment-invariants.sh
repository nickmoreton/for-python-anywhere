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

echo "PASS: deployment static invariants"
