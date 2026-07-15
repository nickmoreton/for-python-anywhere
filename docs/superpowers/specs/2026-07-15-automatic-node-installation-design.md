# Automatic Node Installation During PythonAnywhere Deployment

## Purpose

Prevent a PythonAnywhere deployment from failing merely because the exact Node.js version newly pinned in `.nvmrc` has not already been installed on the server.

## Scope

The deployment will continue to use NVM from `$HOME/nvm` and will continue to treat `.nvmrc` as the authoritative Node.js version. It will automatically install that Node.js version when absent and activate it before installing or building frontend dependencies.

Installing or upgrading NVM itself remains a one-time, manual PythonAnywhere setup step. The deployment will not download or replace NVM automatically.

## Deployment Behavior

After fast-forwarding the server checkout and synchronizing Python dependencies, `scripts/deploy.sh` will:

1. Set `NVM_DIR` to `$HOME/nvm`.
2. Source `$NVM_DIR/nvm.sh`.
3. Run `nvm install` from the repository root.
4. Run `npm ci`.
5. Run `npm run build`.
6. Continue with Django checks, migrations, static collection, and WSGI reload.

Running `nvm install` without an explicit version makes NVM read `.nvmrc`. When that version is already installed, NVM activates it without downloading it again. When it is absent, NVM downloads, installs, and activates the exact pinned version.

## Failure Handling

The deployment script's existing strict error handling will treat any NVM sourcing or Node.js installation failure as fatal. A failure must occur before npm commands, Django operations, static collection, or WSGI reload. The existing deployment error trap will report the nonzero status.

The deployment will not fall back to a different Node.js version. This preserves reproducibility across host development, Docker, CI, and PythonAnywhere.

## Tests

The deployment invariant test will require `nvm install` to appear after NVM is sourced and before `npm ci`.

The deployment failure test will simulate an `nvm install` failure and verify that:

- the deployment returns the NVM failure status;
- npm installation and builds are not attempted;
- Django management commands are not attempted; and
- the WSGI file is not reloaded.

Existing frontend build and deployment tests will continue to verify the complete asset pipeline.

## Documentation

The PythonAnywhere runbook will state that deployments automatically install the `.nvmrc` version when necessary. Its one-time setup will still install NVM and may install the initial pinned Node.js version as an immediate environment verification step.
