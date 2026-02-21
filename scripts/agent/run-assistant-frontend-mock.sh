#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"

export ASSISTANT_FRONTEND_MOCK_API=${ASSISTANT_FRONTEND_MOCK_API:-true}

cd "${ROOT_DIR}/apps/assistant-frontend"
npm run dev -- --host 0.0.0.0 --port 5173
