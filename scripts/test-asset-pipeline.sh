#!/usr/bin/env bash
set -Eeuo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

[[ -f .nvmrc ]] || fail ".nvmrc is missing"
[[ $(<.nvmrc) == 24.18.0 ]] || fail ".nvmrc does not pin Node 24.18.0"
[[ -f package-lock.json ]] || fail "package-lock.json is missing"
[[ -f assets/scss/app.scss ]] || fail "Sass entry point is missing"
expected_sass_modules=(
    assets/scss/abstracts/_tokens.scss
    assets/scss/abstracts/_mixins.scss
    assets/scss/base/_global.scss
    assets/scss/base/_motion.scss
    assets/scss/components/_button.scss
    assets/scss/components/_status.scss
    assets/scss/pages/_home.scss
    assets/scss/pages/_blog-index.scss
    assets/scss/pages/_blog-post.scss
)

for module in "${expected_sass_modules[@]}"; do
    [[ -f "$module" ]] || fail "Sass module is missing: $module"
done

expected_sass_uses=(
    '@use "abstracts/tokens";'
    '@use "abstracts/mixins";'
    '@use "base/global";'
    '@use "components/button";'
    '@use "components/status";'
    '@use "pages/home";'
    '@use "pages/blog-index";'
    '@use "pages/blog-post";'
    '@use "base/motion";'
)

for use_statement in "${expected_sass_uses[@]}"; do
    grep -Fxq "$use_statement" assets/scss/app.scss \
        || fail "Sass manifest is missing: $use_statement"
done

[[ $(rg -c '^@use ' assets/scss/app.scss) -eq ${#expected_sass_uses[@]} ]] \
    || fail "Sass manifest contains unexpected imports"
if rg -q '[{}]' assets/scss/app.scss; then
    fail "Sass manifest must not emit styles directly"
fi
[[ -f assets/js/app.js ]] || fail "JavaScript entry point is missing"

node <<'NODE'
const manifest = require('./package.json');
const expectedDependencies = {
  sass: '1.101.0',
  esbuild: '0.28.1',
  concurrently: '10.0.3',
};
const expectedInstallScripts = {
  '@parcel/watcher@2.5.6': true,
  'esbuild@0.28.1': true,
};

if (manifest.private !== true) throw new Error('package must be private');
if (manifest.engines?.node !== '24.18.0') throw new Error('Node engine is not pinned');
for (const [name, version] of Object.entries(expectedDependencies)) {
  if (manifest.devDependencies?.[name] !== version) {
    throw new Error(`${name} is not pinned to ${version}`);
  }
}
for (const script of ['build', 'build:css', 'build:js', 'dev', 'dev:css', 'dev:js', 'test']) {
  if (!manifest.scripts?.[script]) throw new Error(`missing npm script: ${script}`);
}
if (JSON.stringify(manifest.allowScripts) !== JSON.stringify(expectedInstallScripts)) {
  throw new Error('install-script approvals are not pinned');
}
NODE

grep -Fxq 'node_modules/' .gitignore || fail "node_modules is not ignored"
grep -Fxq 'app/static/css/app.css' .gitignore || fail "generated CSS is not ignored"
grep -Fxq 'app/static/js/app.js' .gitignore || fail "generated JavaScript is not ignored"

rm -f app/static/css/app.css app/static/js/app.js
npm run build
[[ -s app/static/css/app.css ]] || fail "production CSS was not generated"
[[ -s app/static/js/app.js ]] || fail "production JavaScript was not generated"

rg -q 'Node 24\.18\.0' AGENTS.md || fail "AGENTS.md does not document the Node version"
rg -q 'npm ci' AGENTS.md || fail "AGENTS.md does not document locked npm installation"
rg -q 'npm run dev' AGENTS.md || fail "AGENTS.md does not document the watch workflow"
rg -q 'npm run build' AGENTS.md || fail "AGENTS.md does not document the production build"
rg -q 'The `assets` service runs `npm run dev` automatically' AGENTS.md \
    || fail "AGENTS.md does not document automatic Compose watching"

echo "PASS: asset pipeline"
