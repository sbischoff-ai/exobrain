#!/usr/bin/env bash
set -euo pipefail

apps=(
  "assistant-backend"
  "model-provider"
  "job-orchestrator"
  "assistant-frontend"
  "knowledge-interface"
)

for app in "${apps[@]}"; do
  echo "==> Running checks for apps/${app}"
  (
    cd "apps/${app}"
    ./scripts/verify.sh
  )
done
