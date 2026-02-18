# Codex Runbook (Cloud Agent)

Use this runbook in environments where Docker/k3d are unavailable.

## 1) Validate available tools (no installs assumed)

```sh
command -v psql nats-server qdrant reshape uv npm cargo
```

If a tool is missing, continue with tasks that do not require it.

## 2) Native infra startup (when needed)

Start only the services required for your task.

Examples:

```sh
# NATS
nats-server -p 14222 -m 18222

# Qdrant (default config)
qdrant
```

Postgres may be managed as a system service depending on environment policy.

## 3) Build loop

```sh
./scripts/local/build-assistant-backend.sh
./scripts/local/build-assistant-frontend.sh
./scripts/local/build-knowledge-interface.sh
```

## 4) Run loop (separate terminals)

```sh
./scripts/local/run-assistant-backend.sh
./scripts/local/run-assistant-frontend.sh
./scripts/local/run-knowledge-interface.sh
```

## 5) Fast checks

```sh
# Backend unit tests
cd apps/assistant-backend && uv run --with pytest --with pytest-asyncio pytest

# Frontend tests
cd apps/assistant-frontend && npm test
```

## 6) Common issues

- Missing tool binary in environment -> skip dependent task and report limitation.
- Port already in use -> identify conflicting process and choose an open port when possible.
- Reshape not available -> DB migration workflows cannot run; report explicitly.
