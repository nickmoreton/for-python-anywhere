#!/usr/bin/env bash
set -Eeuo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

for workflow in .github/workflows/ci.yml .github/workflows/deploy.yml; do
    rg -q 'uses: actions/setup-node@v4' "$workflow" \
        || fail "$workflow does not set up Node"
    rg -q 'node-version-file: \.nvmrc' "$workflow" \
        || fail "$workflow does not read .nvmrc"
    rg -q 'cache: npm' "$workflow" \
        || fail "$workflow does not cache npm downloads"
    rg -q 'run: npm ci' "$workflow" \
        || fail "$workflow does not use npm ci"
    rg -q 'run: npm run build' "$workflow" \
        || fail "$workflow does not build assets"
done

echo "PASS: workflow asset integration"
