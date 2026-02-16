# Exobrain Assistant Backend

FastAPI service for chat orchestration and GraphRAG context augmentation.

## Local build and run

From the repository root:

```bash
./scripts/local/build-assistant-backend.sh
./scripts/local/run-assistant-backend.sh
```

Notes:
- The build script keeps `.venv` in sync via `uv sync` and only updates dependencies when needed.
- Python is interpreted at runtime; rebuild is mainly needed when dependencies or packaging metadata change.
