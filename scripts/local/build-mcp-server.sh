#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/../.." && pwd)"
app_dir="${repo_root}/apps/mcp-server"

cd "${app_dir}"

# Creates/updates .venv only when dependency metadata changed.
uv sync --extra dev

# Produces bytecode for changed files; no-op for unchanged sources.
uv run python -m compileall -q app

echo "mcp-server dependencies synced and sources compiled"
