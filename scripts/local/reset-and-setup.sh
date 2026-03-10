#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/../.." && pwd)"

run_step() {
  local description="$1"
  shift

  echo
  echo "==> ${description}"
  "$@"
}

cd "${repo_root}"

run_step "start local infrastructure" ./scripts/local/infra-up.sh

run_step "reset knowledge graph stores (memgraph + qdrant)" ./scripts/local/knowledge-graph-reset.sh
run_step "migrate and reset assistant database with seed data" ./scripts/local/assistant-db-migrate.sh
run_step "truncate and reseed assistant database" ./scripts/local/assistant-db-reset-and-seed.sh
run_step "migrate and reset knowledge schema with seed data" ./scripts/local/knowledge-schema-reset-and-seed.sh
run_step "migrate job orchestrator database" ./scripts/local/job-orchestrator-db-setup.sh

run_step "build assistant backend" ./scripts/local/build-assistant-backend.sh
run_step "build assistant frontend" ./scripts/local/build-assistant-frontend.sh
run_step "build job orchestrator" ./scripts/local/build-job-orchestrator.sh
run_step "build knowledge interface" ./scripts/local/build-knowledge-interface.sh
run_step "build mcp server" ./scripts/local/build-mcp-server.sh
run_step "build model provider" ./scripts/local/build-model-provider.sh

echo

echo "Local reset-and-setup complete."
echo "Next: run ./scripts/local/run-fullstack-suite.sh (or your preferred suite script)."
