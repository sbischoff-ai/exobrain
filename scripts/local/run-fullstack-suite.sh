#!/usr/bin/env bash
set -euo pipefail

if ! command -v mprocs >/dev/null 2>&1; then
  echo "mprocs is required. Add it to your PATH or enter nix-shell." >&2
  exit 1
fi

CONFIG=${MPROCS_CONFIG:-.mprocs/fullstack.yml}

exec mprocs --config "$CONFIG"
