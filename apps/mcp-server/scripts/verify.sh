#!/usr/bin/env bash
set -euo pipefail

uv run --extra dev ruff check .
uv run --extra dev python -m compileall app tests
uv run --extra dev pytest
