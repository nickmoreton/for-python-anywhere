#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
deploy_script=$script_dir/deploy.sh
expected_commit=0123456789abcdef0123456789abcdef01234567

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

make_command() {
    local path=$1
    shift
    {
        printf '%s\n' '#!/usr/bin/env bash'
        printf '%s\n' "$@"
    } > "$path"
    chmod +x "$path"
}

setup_case() {
    GIT_STATUS_EXIT=0
    MYSQLDUMP_EXIT=0
    COLLECTSTATIC_EXIT=0
    NODE_CLEANUP_EXIT=0
    case_dir=$(mktemp -d)
    home=$case_dir/home
    repository=$case_dir/repository
    bin=$case_dir/bin
    log=$case_dir/commands.log
    mkdir -p "$home/nvm" "$repository/.venv/bin" "$bin"
    : > "$home/.my.cnf"
    : > "$repository/.env"
    : > "$repository/wsgi.py"

    make_command "$repository/.venv/bin/python" 'printf "%s\n" test_database'
    make_command "$bin/flock" 'exit 0'
    make_command "$bin/uv" \
        'printf "uv %s\n" "$*" >> "$COMMAND_LOG"' \
        'if [[ "$*" == run\ python\ manage.py\ collectstatic\ * ]]; then exit "${COLLECTSTATIC_EXIT:-0}"; fi' \
        'exit 0'
    cat > "$home/nvm/nvm.sh" <<'NVM'
nvm() {
    printf "nvm %s\n" "$*" >> "$COMMAND_LOG"
    return "${NVM_EXIT:-0}"
}
NVM
    make_command "$bin/npm" \
        'printf "npm %s\n" "$*" >> "$COMMAND_LOG"' \
        'if [[ "$*" == "run build" ]]; then exit "${NPM_BUILD_EXIT:-0}"; fi' \
        'exit 0'
    make_command "$bin/rm" \
        'if [[ "$*" == "-rf -- node_modules" && "${NODE_CLEANUP_EXIT:-0}" != 0 ]]; then exit "$NODE_CLEANUP_EXIT"; fi' \
        '/bin/rm "$@"'
    make_command "$bin/touch" \
        '/usr/bin/touch "$@"' \
        '[[ "$1" == */wsgi.py ]] && /usr/bin/touch "$1.reloaded"'
    make_command "$bin/git" \
        'printf "git %s\n" "$*" >> "$COMMAND_LOG"' \
        'case "$1 $2" in' \
        '    "status --porcelain") exit "${GIT_STATUS_EXIT:-0}" ;;' \
        '    "rev-parse origin/main") printf "%s\n" "$EXPECTED_COMMIT" ;;' \
        '    "rev-parse --short") printf "%s\n" "${EXPECTED_COMMIT:0:7}" ;;' \
        'esac' \
        'exit 0'
    make_command "$bin/mysqldump" \
        'printf "%s\n" mysqldump >> "$COMMAND_LOG"' \
        'printf "%s\n" database-dump' \
        'exit "${MYSQLDUMP_EXIT:-0}"'
}

run_deploy() {
    set +e
    output=$(
        HOME=$home \
        PATH=$bin:/usr/bin:/bin \
        COMMAND_LOG=$log \
        EXPECTED_COMMIT=$expected_commit \
        GIT_STATUS_EXIT=${GIT_STATUS_EXIT:-0} \
        MYSQLDUMP_EXIT=${MYSQLDUMP_EXIT:-0} \
        NVM_EXIT=${NVM_EXIT:-0} \
        NPM_BUILD_EXIT=${NPM_BUILD_EXIT:-0} \
        COLLECTSTATIC_EXIT=${COLLECTSTATIC_EXIT:-0} \
        NODE_CLEANUP_EXIT=${NODE_CLEANUP_EXIT:-0} \
        bash "$deploy_script" "$repository" "$repository/wsgi.py" "$expected_commit" 2>&1
    )
    status=$?
    set -e
}

test_git_status_failure_aborts() {
    setup_case
    GIT_STATUS_EXIT=42 run_deploy
    [[ $status == 42 ]] || fail "git status failure returned $status: $output"
    ! grep -q 'git fetch' "$log" || fail "deployment fetched after git status failed"
    rm -rf "$case_dir"
    echo "PASS: git status failure aborts before fetch"
}

test_retention_pipeline_failure_aborts() {
    local failed_command=$1
    local failure_status=$2
    setup_case
    make_command "$bin/find" 'printf "1.0 %s\n" "$HOME/mysql-backups/for-python-anywhere/backup.sql.gz"'
    make_command "$bin/sort" '/bin/cat'
    make_command "$bin/cut" '/bin/cat'
    make_command "$bin/$failed_command" "exit $failure_status"
    run_deploy
    [[ $status == "$failure_status" ]] || fail "$failed_command failure returned $status: $output"
    ! grep -q 'git merge --ff-only' "$log" || fail "deployment merged after $failed_command failed"
    rm -rf "$case_dir"
    echo "PASS: retention $failed_command failure aborts before merge"
}

test_failed_backup_preserves_final() {
    local failed_command=$1
    local failure_status=$2
    setup_case
    backup_dir=$home/mysql-backups/for-python-anywhere
    final_backup=$backup_dir/20260713T120000Z.sql.gz
    mkdir -p "$backup_dir"
    printf '%s\n' valid-existing-backup > "$final_backup"
    make_command "$bin/date" 'printf "%s\n" 20260713T120000Z'

    if [[ $failed_command == gzip ]]; then
        make_command "$bin/gzip" 'printf "%s\n" partial-compressed-data' "exit $failure_status"
    else
        MYSQLDUMP_EXIT=$failure_status
    fi

    run_deploy
    [[ $status == "$failure_status" ]] || fail "$failed_command failure returned $status: $output"
    [[ $(<"$final_backup") == valid-existing-backup ]] || fail "$failed_command failure replaced the valid backup"
    if find "$backup_dir" -maxdepth 1 -type f -name '.backup.*.tmp' | grep -q .; then
        fail "$failed_command failure left a temporary backup"
    fi
    rm -rf "$case_dir"
    echo "PASS: $failed_command failure preserves final backup and removes temp file"
}

test_backup_publication_collision_aborts() {
    setup_case
    backup_dir=$home/mysql-backups/for-python-anywhere
    mkdir -p "$backup_dir"
    make_command "$bin/date" 'printf "%s\n" 20260713T120000000000000Z'
    make_command "$bin/ln" \
        'for target do :; done' \
        'printf "%s\n" valid-existing-backup > "$target"' \
        '/bin/ln "$@"'

    run_deploy
    [[ $status != 0 ]] || fail "backup publication collision unexpectedly succeeded: $output"
    final_backup=$(find "$backup_dir" -maxdepth 1 -type f -name '*.sql.gz' -print -quit)
    [[ -n "$final_backup" ]] || fail "collision test did not create the competing backup"
    [[ $(<"$final_backup") == valid-existing-backup ]] || fail "collision replaced the valid backup"
    ! grep -q 'git merge --ff-only' "$log" || fail "deployment merged after backup collision"
    if find "$backup_dir" -maxdepth 1 -type f -name '.backup.*.tmp' | grep -q .; then
        fail "backup collision left a temporary backup"
    fi
    rm -rf "$case_dir"
    echo "PASS: backup publication collision aborts without overwriting"
}

test_retention_stays_at_backup_root() {
    setup_case
    backup_dir=$home/mysql-backups/for-python-anywhere
    nested_dir=$backup_dir/nested
    mkdir -p "$nested_dir"
    for index in 1 2 3 4 5 6; do
        printf '%s\n' "root-$index" > "$backup_dir/root-$index.sql.gz"
    done
    printf '%s\n' nested > "$nested_dir/nested.sql.gz"
    make_command "$bin/find" \
        '[[ " $* " == *" -maxdepth 1 "* ]] || exit 48' \
        'order=1' \
        'for backup in "$1"/*.sql.gz; do' \
        '    [[ -e "$backup" ]] && printf "%s %s\n" "$((order++))" "$backup"' \
        'done'

    run_deploy
    [[ $status == 0 ]] || fail "retention-scope deployment returned $status: $output"
    [[ -f "$nested_dir/nested.sql.gz" ]] || fail "retention deleted a nested backup"
    root_count=$(find "$backup_dir" -maxdepth 1 -type f -name '*.sql.gz' | wc -l)
    (( root_count == 5 )) || fail "retention kept $root_count root backups instead of 5"
    rm -rf "$case_dir"
    echo "PASS: retention only removes backups at the backup directory root"
}

test_nvm_install_failure_aborts_before_npm_and_django() {
    setup_case
    make_command "$bin/find" 'exit 0'
    NVM_EXIT=48 run_deploy
    [[ $status == 48 ]] || fail "nvm install failure returned $status: $output"
    grep -q '^nvm install$' "$log" || fail "deployment did not install the pinned Node version"
    ! grep -q '^npm ' "$log" || fail "deployment ran npm after nvm install failed"
    ! grep -q '^uv run python manage.py' "$log" \
        || fail "deployment ran Django operations after nvm install failed"
    [[ ! -e "$repository/wsgi.py.reloaded" ]] \
        || fail "deployment reloaded WSGI after nvm install failed"
    rm -rf "$case_dir"
    echo "PASS: nvm install failure aborts before npm and Django operations"
}

test_npm_build_failure_aborts_before_django_operations() {
    setup_case
    make_command "$bin/find" 'exit 0'
    mkdir -p "$repository/node_modules"
    printf '%s\n' installed > "$repository/node_modules/marker"
    NPM_BUILD_EXIT=49 run_deploy
    [[ $status == 49 ]] || fail "npm build failure returned $status: $output"
    grep -q '^npm ci$' "$log" || fail "deployment did not install locked npm dependencies"
    grep -q '^npm run build$' "$log" || fail "deployment did not attempt the asset build"
    ! grep -q '^uv run python manage.py' "$log" \
        || fail "deployment ran Django operations after asset build failure"
    [[ -e "$repository/node_modules/marker" ]] \
        || fail "asset build failure removed node_modules"
    [[ ! -e "$repository/wsgi.py.reloaded" ]] \
        || fail "deployment reloaded WSGI after asset build failure"
    rm -rf "$case_dir"
    echo "PASS: npm build failure aborts before Django operations"
}

test_successful_deployment_removes_node_modules_before_reload() {
    setup_case
    make_command "$bin/find" 'exit 0'
    mkdir -p "$repository/node_modules"
    printf '%s\n' installed > "$repository/node_modules/marker"

    run_deploy

    [[ $status == 0 ]] || fail "successful cleanup deployment returned $status: $output"
    [[ ! -e "$repository/node_modules" ]] \
        || fail "successful deployment left node_modules in place"
    [[ -e "$repository/wsgi.py.reloaded" ]] \
        || fail "successful deployment did not reload WSGI"
    rm -rf "$case_dir"
    echo "PASS: successful deployment removes node_modules before reload"
}

test_successful_deployment_publishes_revision_before_reload() {
    setup_case
    make_command "$bin/find" 'exit 0'

    run_deploy

    [[ $status == 0 ]] || fail "successful revision deployment returned $status: $output"
    [[ -f "$repository/.deployed-commit" ]] \
        || fail "successful deployment did not publish its revision"
    [[ $(<"$repository/.deployed-commit") == "$expected_commit" ]] \
        || fail "deployment published the wrong revision"
    [[ -e "$repository/wsgi.py.reloaded" ]] \
        || fail "deployment did not reload WSGI after publishing its revision"
    rm -rf "$case_dir"
    echo "PASS: successful deployment publishes revision before reload"
}

test_collectstatic_failure_preserves_node_modules() {
    setup_case
    make_command "$bin/find" 'exit 0'
    mkdir -p "$repository/node_modules"
    printf '%s\n' installed > "$repository/node_modules/marker"

    COLLECTSTATIC_EXIT=50 run_deploy

    [[ $status == 50 ]] || fail "collectstatic failure returned $status: $output"
    [[ -e "$repository/node_modules/marker" ]] \
        || fail "collectstatic failure removed node_modules"
    [[ ! -e "$repository/wsgi.py.reloaded" ]] \
        || fail "deployment reloaded WSGI after collectstatic failure"
    rm -rf "$case_dir"
    echo "PASS: collectstatic failure preserves node_modules and skips reload"
}

test_node_modules_cleanup_failure_aborts_before_reload() {
    setup_case
    make_command "$bin/find" 'exit 0'
    mkdir -p "$repository/node_modules"
    printf '%s\n' installed > "$repository/node_modules/marker"

    NODE_CLEANUP_EXIT=51 run_deploy

    [[ $status == 51 ]] || fail "node_modules cleanup failure returned $status: $output"
    [[ -e "$repository/node_modules/marker" ]] \
        || fail "failed cleanup unexpectedly removed node_modules"
    [[ ! -e "$repository/wsgi.py.reloaded" ]] \
        || fail "deployment reloaded WSGI after cleanup failure"
    rm -rf "$case_dir"
    echo "PASS: node_modules cleanup failure aborts before reload"
}

case ${1:-all} in
    git-status) test_git_status_failure_aborts ;;
    retention-find) test_retention_pipeline_failure_aborts find 43 ;;
    retention-sort) test_retention_pipeline_failure_aborts sort 46 ;;
    retention-cut) test_retention_pipeline_failure_aborts cut 47 ;;
    gzip) test_failed_backup_preserves_final gzip 44 ;;
    mysqldump) test_failed_backup_preserves_final mysqldump 45 ;;
    collision) test_backup_publication_collision_aborts ;;
    retention-scope) test_retention_stays_at_backup_root ;;
    nvm-install) test_nvm_install_failure_aborts_before_npm_and_django ;;
    npm-build) test_npm_build_failure_aborts_before_django_operations ;;
    cleanup-success) test_successful_deployment_removes_node_modules_before_reload ;;
    revision-success) test_successful_deployment_publishes_revision_before_reload ;;
    collectstatic) test_collectstatic_failure_preserves_node_modules ;;
    cleanup-failure) test_node_modules_cleanup_failure_aborts_before_reload ;;
    all)
        test_git_status_failure_aborts
        test_retention_pipeline_failure_aborts find 43
        test_retention_pipeline_failure_aborts sort 46
        test_retention_pipeline_failure_aborts cut 47
        test_failed_backup_preserves_final gzip 44
        test_failed_backup_preserves_final mysqldump 45
        test_backup_publication_collision_aborts
        test_retention_stays_at_backup_root
        test_nvm_install_failure_aborts_before_npm_and_django
        test_npm_build_failure_aborts_before_django_operations
        test_successful_deployment_removes_node_modules_before_reload
        test_successful_deployment_publishes_revision_before_reload
        test_collectstatic_failure_preserves_node_modules
        test_node_modules_cleanup_failure_aborts_before_reload
        ;;
    *) fail "unknown test: $1" ;;
esac
