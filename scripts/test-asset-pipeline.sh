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
[[ -f assets/js/app.js ]] || fail "JavaScript entry point is missing"

node <<'NODE'
const manifest = require('./package.json');
const expectedDependencies = {
  sass: '1.101.0',
  esbuild: '0.28.1',
  concurrently: '10.0.3',
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
NODE

grep -Fxq 'node_modules/' .gitignore || fail "node_modules is not ignored"
grep -Fxq 'app/static/css/app.css' .gitignore || fail "generated CSS is not ignored"
grep -Fxq 'app/static/js/app.js' .gitignore || fail "generated JavaScript is not ignored"

rm -f app/static/css/app.css app/static/js/app.js
npm run build
[[ -s app/static/css/app.css ]] || fail "production CSS was not generated"
[[ -s app/static/js/app.js ]] || fail "production JavaScript was not generated"

echo "PASS: asset pipeline"
