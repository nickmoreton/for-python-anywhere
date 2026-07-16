# PythonAnywhere `node_modules` Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `node_modules` from the PythonAnywhere repository checkout after all build and Django deployment operations succeed, immediately before WSGI reload.

**Architecture:** Keep the existing locked npm build in `scripts/deploy.sh`, then add one explicit cleanup boundary between `collectstatic` and the WSGI reload. Extend the shell test harness to exercise successful cleanup, pre-cleanup failure, and cleanup failure; keep documentation assertions in the existing deployment-invariant test.

**Tech Stack:** Bash, npm with Node.js 24.18.0 through NVM, Django/Wagtail management commands, ripgrep-based shell integration tests.

## Global Constraints

- Cleanup applies only to frontend builds performed directly in the PythonAnywhere repository checkout.
- Local host development, Docker Compose, Docker image builds, and GitHub Actions retain their existing dependency handling.
- Cleanup runs only after `npm run build` and the subsequent Django deployment operations exit successfully.
- Cleanup is `rm -rf -- node_modules` and runs after `collectstatic` but before `touch "$wsgi_file"`.
- Any failure before cleanup leaves `node_modules` in place and does not reload WSGI.
- Cleanup failure aborts before WSGI reload.
- Generated CSS and JavaScript remain outside `node_modules`.

---

## File Structure

- `scripts/deploy.sh`: owns the ordered PythonAnywhere deployment and the new cleanup boundary.
- `scripts/test-deploy-failures.sh`: executes the deployment against controlled command doubles and verifies cleanup success and failure behavior.
- `scripts/test-deployment-invariants.sh`: enforces cleanup ordering and the documented bootstrap sequence statically.
- `docs/pythonanywhere.md`: tells operators when initial-setup dependencies are removed and explains failure retention.
- `AGENTS.md`: records the updated supported PythonAnywhere deployment workflow.

### Task 1: Deployment cleanup and failure behavior

**Files:**
- Modify: `scripts/test-deploy-failures.sh:23-217`
- Modify: `scripts/test-deployment-invariants.sh:52-64`
- Modify: `scripts/deploy.sh:96-108`

**Interfaces:**
- Consumes: the existing `run_deploy` harness, `NPM_BUILD_EXIT`, command log, and `wsgi.py.reloaded` marker.
- Produces: `rm -rf -- node_modules` after successful `collectstatic`; `COLLECTSTATIC_EXIT` and `NODE_CLEANUP_EXIT` harness controls; `cleanup-success`, `collectstatic`, and `cleanup-failure` test selectors.

- [ ] **Step 1: Extend the deployment test harness and add behavioral tests**

In `setup_case`, initialize the new controls beside the existing exit controls:

```bash
setup_case() {
    GIT_STATUS_EXIT=0
    MYSQLDUMP_EXIT=0
    COLLECTSTATIC_EXIT=0
    NODE_CLEANUP_EXIT=0
```

Replace the `uv` command double with:

```bash
    make_command "$bin/uv" \
        'printf "uv %s\n" "$*" >> "$COMMAND_LOG"' \
        'if [[ "$*" == run\ python\ manage.py\ collectstatic\ * ]]; then exit "${COLLECTSTATIC_EXIT:-0}"; fi' \
        'exit 0'
```

Add an `rm` command double immediately after the `npm` command double. It delegates every unrelated removal to the system command and makes only the new cleanup operation controllably fallible:

```bash
    make_command "$bin/rm" \
        'if [[ "$*" == "-rf -- node_modules" && "${NODE_CLEANUP_EXIT:-0}" != 0 ]]; then exit "$NODE_CLEANUP_EXIT"; fi' \
        '/bin/rm "$@"'
```

Pass both controls through `run_deploy`:

```bash
        MYSQLDUMP_EXIT=${MYSQLDUMP_EXIT:-0} \
        NPM_BUILD_EXIT=${NPM_BUILD_EXIT:-0} \
        COLLECTSTATIC_EXIT=${COLLECTSTATIC_EXIT:-0} \
        NODE_CLEANUP_EXIT=${NODE_CLEANUP_EXIT:-0} \
        bash "$deploy_script" "$repository" "$repository/wsgi.py" "$expected_commit" 2>&1
```

Add these functions after `test_npm_build_failure_aborts_before_django_operations`:

```bash
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
```

In the existing npm-build failure test, create a marker before `run_deploy` and assert it remains afterward:

```bash
    mkdir -p "$repository/node_modules"
    printf '%s\n' installed > "$repository/node_modules/marker"
    NPM_BUILD_EXIT=49 run_deploy
```

```bash
    [[ -e "$repository/node_modules/marker" ]] \
        || fail "asset build failure removed node_modules"
```

Add selectors and all-suite calls:

```bash
    cleanup-success) test_successful_deployment_removes_node_modules_before_reload ;;
    collectstatic) test_collectstatic_failure_preserves_node_modules ;;
    cleanup-failure) test_node_modules_cleanup_failure_aborts_before_reload ;;
```

```bash
        test_npm_build_failure_aborts_before_django_operations
        test_successful_deployment_removes_node_modules_before_reload
        test_collectstatic_failure_preserves_node_modules
        test_node_modules_cleanup_failure_aborts_before_reload
```

- [ ] **Step 2: Add the failing static ordering invariant**

In `scripts/test-deployment-invariants.sh`, capture the cleanup line with the other deployment line numbers:

```bash
deploy_cleanup_line=$(rg -n '^rm -rf -- node_modules$' scripts/deploy.sh | cut -d: -f1)
```

Replace the ordering assertion with:

```bash
(( deploy_nvm_line < deploy_ci_line \
    && deploy_ci_line < deploy_build_line \
    && deploy_build_line < deploy_migrate_line \
    && deploy_migrate_line < deploy_collectstatic_line \
    && deploy_collectstatic_line < deploy_cleanup_line \
    && deploy_cleanup_line < deploy_reload_line )) \
    || fail "frontend build, Django operations, cleanup, and reload are incorrectly ordered"
```

- [ ] **Step 3: Run the focused tests to verify they fail**

Run:

```bash
bash scripts/test-deploy-failures.sh cleanup-success
bash scripts/test-deploy-failures.sh cleanup-failure
bash scripts/test-deployment-invariants.sh
```

Expected: `cleanup-success` fails because `node_modules` remains; `cleanup-failure` fails because no cleanup command returns status 51; the invariant test exits non-zero because `scripts/deploy.sh` has no cleanup line.

- [ ] **Step 4: Add the minimal deployment cleanup**

Insert one line after `collectstatic` and before WSGI reload in `scripts/deploy.sh`:

```bash
uv run python manage.py collectstatic --noinput --clear --settings=app.settings.production
rm -rf -- node_modules
touch "$wsgi_file"
```

- [ ] **Step 5: Run the deployment tests and syntax checks**

Run:

```bash
bash -n scripts/deploy.sh
bash -n scripts/test-deploy-failures.sh
bash -n scripts/test-deployment-invariants.sh
bash scripts/test-deploy-failures.sh
bash scripts/test-deployment-invariants.sh
```

Expected: syntax checks exit zero; every failure-harness case prints `PASS`; the invariant script prints `PASS: deployment static invariants`.

- [ ] **Step 6: Commit the deployment behavior**

```bash
git add scripts/deploy.sh scripts/test-deploy-failures.sh scripts/test-deployment-invariants.sh
git commit -m "deploy: remove Node dependencies before reload"
```

### Task 2: PythonAnywhere operator and repository guidance

**Files:**
- Modify: `scripts/test-deployment-invariants.sh:66-73`
- Modify: `docs/pythonanywhere.md:123-132`
- Modify: `AGENTS.md:88-92`

**Interfaces:**
- Consumes: the cleanup command and ordering established by Task 1.
- Produces: an initial-setup sequence of build, `collectstatic`, cleanup, and superuser creation; repository guidance that describes automated cleanup before reload.

- [ ] **Step 1: Write failing documentation invariants**

Append these checks before the final success message in `scripts/test-deployment-invariants.sh`:

```bash
initial_setup_block=$(
    sed -n \
        '/^Apply the initial database and static setup:/,/^Create a manual-configuration PythonAnywhere WSGI web app/p' \
        docs/pythonanywhere.md
)
setup_build_line=$(rg -n '^npm run build$' <<< "$initial_setup_block" | cut -d: -f1)
setup_collectstatic_line=$(rg -n '^uv run python manage.py collectstatic ' <<< "$initial_setup_block" | cut -d: -f1)
setup_cleanup_line=$(rg -n '^rm -rf -- node_modules$' <<< "$initial_setup_block" | cut -d: -f1)

(( setup_build_line < setup_collectstatic_line \
    && setup_collectstatic_line < setup_cleanup_line )) \
    || fail "runbook does not clean node_modules after initial static collection"

rg -q 'removes `node_modules` immediately before reloading WSGI' AGENTS.md \
    || fail "repository guide does not document PythonAnywhere Node cleanup"
```

- [ ] **Step 2: Run the invariant test to verify it fails**

Run:

```bash
bash scripts/test-deployment-invariants.sh
```

Expected: FAIL because the initial-setup block has no `rm -rf -- node_modules` line and `AGENTS.md` does not describe cleanup.

- [ ] **Step 3: Update the PythonAnywhere runbook**

Change the initial database and static setup block in `docs/pythonanywhere.md` to:

```bash
uv run python manage.py check --deploy --settings=app.settings.production
uv run python manage.py migrate --noinput --settings=app.settings.production
npm ci
npm run build
uv run python manage.py collectstatic --noinput --clear --settings=app.settings.production
rm -rf -- node_modules
uv run python manage.py createsuperuser --settings=app.settings.production
```

Add this paragraph immediately after the block:

```markdown
The final cleanup removes build-only Node dependencies after static files have been collected. If an earlier command fails, `node_modules` remains available for diagnosis; rerun `npm ci` before retrying the build.
```

- [ ] **Step 4: Update repository deployment guidance**

Replace the PythonAnywhere deployment-detail paragraph in `AGENTS.md` with:

```markdown
During deployment, the remote script sources NVM from `$HOME/nvm`, installs locked frontend dependencies with `npm ci`, runs `npm run build`, completes the Django deployment operations, removes `node_modules` immediately before reloading WSGI, and then verifies the public site through the workflow. Node is a build tool only and does not serve the website. See `docs/pythonanywhere.md` for bootstrap, GitHub variables and secrets, deployment operation, and recovery.
```

- [ ] **Step 5: Run documentation and deployment checks**

Run:

```bash
bash scripts/test-deployment-invariants.sh
bash scripts/test-deploy-failures.sh
git diff --check
```

Expected: both scripts print their `PASS` output, `git diff --check` prints nothing, and all commands exit zero.

- [ ] **Step 6: Commit the operator guidance**

```bash
git add scripts/test-deployment-invariants.sh docs/pythonanywhere.md AGENTS.md
git commit -m "docs: document PythonAnywhere Node cleanup"
```

### Task 3: Full regression verification

**Files:**
- Verify only; no planned file changes.

**Interfaces:**
- Consumes: the deployment cleanup behavior and documentation from Tasks 1 and 2.
- Produces: evidence that the complete repository remains valid under its configured backend, frontend, container, workflow, and deployment checks.

- [ ] **Step 1: Run the shell integration suite**

Run:

```bash
bash scripts/test-asset-pipeline.sh
bash scripts/test-container-assets.sh
bash scripts/test-workflow-assets.sh
bash scripts/test-deployment-invariants.sh
bash scripts/test-deploy-failures.sh
```

Expected: every script prints only its expected `PASS` results and exits zero.

- [ ] **Step 2: Run Django/Wagtail regression checks**

Run against the configured host MySQL database:

```bash
uv run python manage.py test
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Expected: the test suite passes, Django reports no system-check issues, and Django reports `No changes detected`.

- [ ] **Step 3: Inspect final repository state**

Run:

```bash
git diff --check
git status --short
git log -5 --oneline
```

Expected: `git diff --check` prints nothing; status contains no unintended files; the log contains the focused deployment and documentation commits from Tasks 1 and 2.
