#!/usr/bin/env bash
set -euo pipefail

export APP_ENV=${APP_ENV:-local}
export MODEL_PROVIDER_CONFIG_PATH=${MODEL_PROVIDER_CONFIG_PATH:-config/models.yaml}

cd apps/model-provider
uv run uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
