#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/../.." && pwd)"
app_dir="${repo_root}/apps/knowledge-interface"

cd "${app_dir}"

# Cargo reuses incremental artifacts and only recompiles what changed.
cargo build
