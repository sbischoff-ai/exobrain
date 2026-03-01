#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
E2E_DIR="${ROOT_DIR}/e2e"

FORCE_REINSTALL="${E2E_FORCE_REINSTALL:-false}"
if [[ "${1:-}" == "--force-reinstall" ]]; then
  FORCE_REINSTALL=true
fi

if [[ ! -d "${E2E_DIR}" ]]; then
  echo "❌ e2e directory not found: ${E2E_DIR}" >&2
  exit 20
fi

cd "${E2E_DIR}"

install_cmd="npm install"
if [[ -f package-lock.json ]]; then
  install_cmd="npm ci"
fi

need_install=false
if [[ "${FORCE_REINSTALL}" == "true" ]]; then
  need_install=true
  echo "ℹ️  Dependency reinstall forced (E2E_FORCE_REINSTALL=true or --force-reinstall)."
elif [[ ! -d node_modules ]]; then
  need_install=true
  echo "ℹ️  node_modules not found; installing dependencies."
elif ! npm ls --depth=0 --silent >/dev/null 2>&1; then
  need_install=true
  echo "ℹ️  Existing node_modules is invalid; reinstalling dependencies."
else
  echo "✅ Reusing existing node_modules (set E2E_FORCE_REINSTALL=true to reinstall)."
fi

if [[ "${need_install}" == "true" ]]; then
  echo "▶ ${install_cmd}"
  if ! ${install_cmd}; then
    echo "❌ Failed to install E2E dependencies." >&2
    echo "Hint: verify Node/npm are installed and rerun '${install_cmd}' in e2e/." >&2
    exit 21
  fi
fi

if ! npx playwright --version >/dev/null 2>&1; then
  echo "❌ Playwright CLI is unavailable after dependency setup." >&2
  echo "Hint: rerun '${install_cmd}' in e2e/ and check npm output for missing deps." >&2
  exit 22
fi

server_mode="managed"
if [[ "${E2E_USE_EXISTING_SERVER:-false}" == "true" ]]; then
  server_mode="existing"
  echo "ℹ️  E2E_USE_EXISTING_SERVER=true: Playwright will use your existing frontend server."
else
  echo "ℹ️  E2E_USE_EXISTING_SERVER is not true: Playwright will manage the frontend web server."
fi

echo "▶ npm test"
if ! npm test; then
  echo "❌ Frontend E2E run failed." >&2
  echo "Hint: if the error references missing browsers, run 'cd e2e && npx playwright install'." >&2
  echo "Hint: if the error references missing modules, rerun this script with --force-reinstall." >&2
  exit 23
fi

echo
echo "E2E summary"
echo "- Server mode: ${server_mode}"
echo "- Re-run: ./scripts/agent/run-assistant-frontend-e2e.sh"
echo "- Force reinstall + re-run: E2E_FORCE_REINSTALL=true ./scripts/agent/run-assistant-frontend-e2e.sh"
echo "- Existing server mode: E2E_USE_EXISTING_SERVER=true ./scripts/agent/run-assistant-frontend-e2e.sh"
