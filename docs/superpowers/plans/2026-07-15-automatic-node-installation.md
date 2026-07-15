# Automatic Node Installation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PythonAnywhere deployments automatically install and activate the exact Node.js version pinned in `.nvmrc` when that version is not already present.

**Architecture:** Keep NVM itself as a manually provisioned PythonAnywhere prerequisite at `$HOME/nvm`, but replace the deployment's activation-only `nvm use` command with NVM's idempotent `nvm install`. Extend the existing shell integration tests to prove installation ordering and fail-closed behavior, then document the automatic provisioning behavior in the runbook.

**Tech Stack:** Bash, NVM, npm, Django staticfiles, shell integration tests using temporary command doubles.

## Global Constraints

- `.nvmrc` remains the authoritative source for the exact Node.js version.
- NVM remains installed manually at `$HOME/nvm`; deployment must not download or upgrade NVM.
- A Node.js installation failure must stop deployment before npm, Django operations, static collection, or WSGI reload.
- Deployment must never fall back to a different Node.js version.
- Generated frontend assets remain ignored and must not be committed.

---

## File Structure

- `scripts/deploy.sh`: source NVM, install or reuse the `.nvmrc` version, and continue with the existing locked frontend build.
- `scripts/test-deploy-failures.sh`: simulate NVM failure and verify that no later deployment boundary is crossed.
- `scripts/test-deployment-invariants.sh`: enforce the static ordering contract for NVM installation before npm and Django operations, plus the runbook contract.
- `docs/pythonanywhere.md`: explain automatic Node.js installation and the remaining manual NVM prerequisite.

### Task 1: Install the pinned Node.js version during deployment

**Files:**
- Modify: `scripts/test-deploy-failures.sh`
- Modify: `scripts/test-deployment-invariants.sh`
- Modify: `scripts/deploy.sh`

**Interfaces:**
- Consumes: `.nvmrc` through NVM's no-argument `nvm install` command and the existing `$HOME/nvm/nvm.sh` installation.
- Produces: a deployment boundary where the exact pinned Node.js version is installed and active before `npm ci`; an `NVM_EXIT` test control for simulating NVM failures.

- [ ] **Step 1: Add the failing NVM failure-path test**

In `scripts/test-deploy-failures.sh`, pass `NVM_EXIT` into the isolated deployment environment by adding this line beside the other injected exit statuses in `run_deploy`:

```bash
        NVM_EXIT=${NVM_EXIT:-0} \
```

Add this test immediately before `test_npm_build_failure_aborts_before_django_operations`:

```bash
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
```

Expose the focused test and include it in the full suite:

```bash
    nvm-install) test_nvm_install_failure_aborts_before_npm_and_django ;;
```

Add this call in the `all)` branch immediately before the npm build failure test:

```bash
        test_nvm_install_failure_aborts_before_npm_and_django
```

- [ ] **Step 2: Strengthen the deployment ordering invariant**

In `scripts/test-deployment-invariants.sh`, add these assertions after the existing NVM source assertion:

```bash
rg -q '^nvm install$' scripts/deploy.sh \
    || fail "deployment does not install the pinned Node version"
! rg -q '^nvm use$' scripts/deploy.sh \
    || fail "deployment still requires the pinned Node version to be preinstalled"
```

Capture the installation line after `deploy_nvm_line`:

```bash
deploy_nvm_install_line=$(rg -n '^nvm install$' scripts/deploy.sh | cut -d: -f1)
```

Replace the first part of the ordering expression with:

```bash
(( deploy_nvm_line < deploy_nvm_install_line \
    && deploy_nvm_install_line < deploy_ci_line \
```

Keep the existing comparisons from `deploy_ci_line < deploy_build_line` through `deploy_build_line < deploy_reload_line` unchanged.

- [ ] **Step 3: Run the focused tests to verify they fail**

Run:

```bash
bash scripts/test-deploy-failures.sh nvm-install
bash scripts/test-deployment-invariants.sh
```

Expected: both commands fail because `scripts/deploy.sh` logs or contains `nvm use`, not `nvm install`.

- [ ] **Step 4: Implement the minimal deployment change**

In `scripts/deploy.sh`, replace:

```bash
nvm use
```

with:

```bash
nvm install
```

Do not add a separate version parser or fallback. NVM must read `.nvmrc`, reuse an installed exact version, or install and activate the missing exact version itself.

- [ ] **Step 5: Run the focused tests to verify they pass**

Run:

```bash
bash scripts/test-deploy-failures.sh nvm-install
bash scripts/test-deployment-invariants.sh
```

Expected:

```text
PASS: nvm install failure aborts before npm and Django operations
PASS: deployment static invariants
```

- [ ] **Step 6: Run the complete deployment failure suite**

Run:

```bash
bash scripts/test-deploy-failures.sh
```

Expected: every deployment failure scenario prints its `PASS:` line, including the new NVM installation scenario, and the command exits zero.

- [ ] **Step 7: Commit the deployment behavior**

```bash
git add scripts/deploy.sh scripts/test-deploy-failures.sh scripts/test-deployment-invariants.sh
git commit -m "fix: install pinned Node during deployment"
```

### Task 2: Document and verify automatic Node.js provisioning

**Files:**
- Modify: `scripts/test-deployment-invariants.sh`
- Modify: `docs/pythonanywhere.md`

**Interfaces:**
- Consumes: the `nvm install` deployment behavior introduced by Task 1.
- Produces: a runbook statement that future operators can rely on and an executable documentation contract protecting that statement.

- [ ] **Step 1: Add the failing runbook contract**

In `scripts/test-deployment-invariants.sh`, add this assertion after the existing check that the runbook documents NVM installation:

```bash
rg -Fq 'automatically installs and activates the exact Node.js version pinned in `.nvmrc`' docs/pythonanywhere.md \
    || fail "runbook does not document automatic pinned Node installation"
```

- [ ] **Step 2: Run the documentation contract to verify it fails**

Run:

```bash
bash scripts/test-deployment-invariants.sh
```

Expected: exit 1 with:

```text
FAIL: runbook does not document automatic pinned Node installation
```

- [ ] **Step 3: Document the deployment behavior**

In `docs/pythonanywhere.md`, add this paragraph to the `## Deploying` section after the paragraph describing a successful workflow run:

```markdown
Before installing frontend dependencies, the remote deployment automatically installs and activates the exact Node.js version pinned in `.nvmrc`. NVM reuses the version when it is already installed and downloads it when it is absent. NVM itself must already exist at `$HOME/nvm` as described in the one-time setup.
```

- [ ] **Step 4: Run the documentation contract to verify it passes**

Run:

```bash
bash scripts/test-deployment-invariants.sh
```

Expected:

```text
PASS: deployment static invariants
```

- [ ] **Step 5: Run all relevant verification**

Run:

```bash
bash scripts/test-asset-pipeline.sh
bash scripts/test-deployment-invariants.sh
bash scripts/test-deploy-failures.sh
git diff --check
```

Expected: each test script prints its `PASS:` output, `git diff --check` produces no output, and all commands exit zero. Generated `app/static/css/app.css`, `app/static/js/app.js`, and `node_modules/` remain ignored.

- [ ] **Step 6: Inspect the final tracked changes**

Run:

```bash
git status --short
git diff -- docs/pythonanywhere.md scripts/test-deployment-invariants.sh
```

Expected: only the Task 2 runbook and invariant-test changes remain uncommitted; no generated frontend assets appear as tracked changes.

- [ ] **Step 7: Commit the documentation contract**

```bash
git add docs/pythonanywhere.md scripts/test-deployment-invariants.sh
git commit -m "docs: explain automatic Node deployment setup"
```
