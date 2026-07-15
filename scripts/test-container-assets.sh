#!/usr/bin/env bash
set -Eeuo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

rg -q '^FROM node:24\.18\.0-bookworm-slim AS frontend$' Dockerfile \
    || fail "Dockerfile is missing the pinned frontend stage"
rg -q '^RUN npm ci$' Dockerfile \
    || fail "Dockerfile does not install locked frontend dependencies"
rg -q '^RUN npm run build$' Dockerfile \
    || fail "Dockerfile does not build frontend assets"
rg -q 'COPY --from=frontend .*app/static/css/app\.css' Dockerfile \
    || fail "Dockerfile does not copy generated CSS"
rg -q 'COPY --from=frontend .*app/static/js/app\.js' Dockerfile \
    || fail "Dockerfile does not copy generated JavaScript"

rg -q '^  assets:$' compose.yaml || fail "Compose assets service is missing"
rg -q 'image: node:24\.18\.0-bookworm-slim' compose.yaml \
    || fail "Compose assets service does not use pinned Node"
rg -q 'npm ci && npm run dev' compose.yaml \
    || fail "Compose assets service does not run the watcher"
rg -q 'node-modules:/app/node_modules' compose.yaml \
    || fail "Compose assets service lacks an isolated node_modules volume"
grep -Fxq 'node_modules/' .dockerignore || fail "node_modules is not excluded from Docker context"

echo "PASS: container asset integration"
