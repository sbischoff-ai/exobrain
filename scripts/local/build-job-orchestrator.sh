#!/usr/bin/env bash
set -euo pipefail

cd apps/job-orchestrator
uv sync --extra dev
python -m compileall app

echo "job-orchestrator dependencies synced and sources compiled"
