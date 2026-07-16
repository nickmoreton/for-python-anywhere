# PythonAnywhere `node_modules` Cleanup Design

**Date:** 2026-07-16

## Goal

Reduce persistent disk usage on PythonAnywhere by removing the repository's `node_modules` directory after frontend assets have been built successfully. Node.js remains a deployment-time build tool and is not required by the running Django application.

## Scope

This change applies only to frontend builds performed directly in the PythonAnywhere repository checkout:

- automated deployments through `scripts/deploy.sh`; and
- the one-time production setup documented in `docs/pythonanywhere.md`.

Local host development, Docker Compose, Docker image builds, and GitHub Actions retain their existing dependency handling.

## Deployment Flow

The automated PythonAnywhere deployment will perform the frontend steps in this order:

1. Activate or install the Node.js version pinned by `.nvmrc`.
2. Run `npm ci` to create a clean dependency installation from `package-lock.json`.
3. Run `npm run build` to generate the production CSS and JavaScript files.
4. Run `rm -rf -- node_modules`.
5. Continue with the production Django check, migrations, static-file collection, and WSGI reload.

The initial PythonAnywhere setup instructions will place the same cleanup command immediately after their successful `npm run build` command.

## Failure Behavior

Cleanup runs only after `npm run build` exits successfully. If `npm ci` or `npm run build` fails, the deployment aborts under the script's existing strict error handling and leaves `node_modules` in place for diagnosis.

If removing `node_modules` itself fails, the deployment aborts before database migration, static-file collection, or application reload. This prevents a deployment from being reported as successful when its disk-cleanup requirement was not satisfied.

The generated CSS and JavaScript files are outside `node_modules`, so removing dependencies does not remove the build output. A later deployment recreates dependencies with `npm ci` before rebuilding.

## Verification

Deployment tests will verify that:

- cleanup is ordered after `npm run build` and before Django mutation or reload operations;
- a successful deployment removes an existing `node_modules` directory;
- a failed frontend build leaves `node_modules` in place and does not run Django operations or reload WSGI; and
- the PythonAnywhere runbook documents cleanup after its initial frontend build.

The existing deployment, asset-pipeline, workflow, and Django checks remain the regression suite. Repository guidance will be updated to state that automated PythonAnywhere deployments remove `node_modules` after successful asset compilation.
