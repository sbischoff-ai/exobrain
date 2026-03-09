#!/usr/bin/env bash
set -euo pipefail

export APP_ENV=${APP_ENV:-local}
export MCP_SERVER_HOST=${MCP_SERVER_HOST:-0.0.0.0}
export MCP_SERVER_PORT=${MCP_SERVER_PORT:-8090}

cd apps/mcp-server
uv run uvicorn app.main:app --host "${MCP_SERVER_HOST}" --port "${MCP_SERVER_PORT}" --reload
