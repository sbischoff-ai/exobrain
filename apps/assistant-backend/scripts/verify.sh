#!/usr/bin/env bash
set -euo pipefail

uv run --extra dev ruff check .
uv run --extra dev python -m compileall app tests
uv run --extra dev pytest tests/integration/test_mcp_tool_bridge_integration.py
uv run --extra dev pytest
