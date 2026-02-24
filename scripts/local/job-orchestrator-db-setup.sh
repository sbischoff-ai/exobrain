#!/usr/bin/env bash
set -euo pipefail

./scripts/local/job-orchestrator-db-migrate.sh

echo "job_orchestrator_db initialized and reshaped"
