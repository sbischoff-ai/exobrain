#!/usr/bin/env bash
set -euo pipefail

RELEASE_NAME=${RELEASE_NAME:-exobrain}
NAMESPACE=${NAMESPACE:-default}
CHART_PATH=${CHART_PATH:-infra/helm/exobrain-stack}

helm upgrade --install "$RELEASE_NAME" "$CHART_PATH" \
  --namespace "$NAMESPACE" \
  --create-namespace \
  --dependency-update \
  --wait \
  --wait-for-jobs \
  --set dbJobs.assistantBackendMigrations.enabled=false \
  --set dbJobs.assistantBackendSeed.enabled=true

echo "assistant-backend metastore seed job completed"
