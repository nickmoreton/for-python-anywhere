# PythonAnywhere `node_modules` Cleanup Design

**Date:** 2026-07-16

## Goal

Reduce persistent disk usage on PythonAnywhere by removing the repository's `node_modules` directory after the frontend build and Django deployment operations have completed successfully. Node.js remains a deployment-time build tool and is not required by the running Django application.

## Scope

This change applies only to frontend builds performed directly in the PythonAnywhere repository checkout:

- automated deployments through `scripts/deploy.sh`; and
- the one-time production setup documented in `docs/pythonanywhere.md`.

Local host development, Docker Compose, Docker image builds, and GitHub Actions retain their existing dependency handling.

## Deployment Flow

The automated PythonAnywhere deployment will perform the relevant steps in this order:

1. Activate or install the Node.js version pinned by `.nvmrc`.
2. Run `npm ci` to create a clean dependency installation from `package-lock.json`.
3. Run `npm run build` to generate the production CSS and JavaScript files.
4. Run the production Django check, migrations, and static-file collection.
5. Run `rm -rf -- node_modules`.
6. Reload WSGI.

The initial PythonAnywhere setup instructions have no WSGI reload step. They will place the cleanup command after their successful static-file collection, once the initial frontend build output has been collected.

## Failure Behavior

Cleanup runs only after `npm run build` and the subsequent Django deployment operations exit successfully. If dependency installation, the frontend build, a Django check, migration, or static-file collection fails, the deployment aborts under the script's existing strict error handling and leaves `node_modules` in place for diagnosis.

If removing `node_modules` itself fails, the deployment aborts before application reload. Database migrations and static-file collection may already have completed, matching the existing deployment order, but the new application version is not activated. This prevents the deployment from reporting a cleanup failure after the WSGI application has already reloaded.

The generated CSS and JavaScript files are outside `node_modules`, so removing dependencies does not remove the build output. A later deployment recreates dependencies with `npm ci` before rebuilding.

## Verification

Deployment tests will verify that:

- cleanup is ordered after `npm run build` and all Django deployment operations, but before WSGI reload;
- a successful deployment removes an existing `node_modules` directory;
- a failure before cleanup leaves `node_modules` in place and does not reload WSGI; and
- the PythonAnywhere runbook documents cleanup after its initial static-file collection.

The existing deployment, asset-pipeline, workflow, and Django checks remain the regression suite. Repository guidance will be updated to state that automated PythonAnywhere deployments remove `node_modules` after the build and Django deployment operations succeed, immediately before WSGI reload.
