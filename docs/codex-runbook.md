# Codex Runbook (Cloud Agent)

Use this runbook when Docker/k3d flows are unavailable.

## Quick start (tested)

```sh
./scripts/agent/native-infra-up.sh
./scripts/agent/native-infra-health.sh
./scripts/agent/assistant-db-setup-native.sh
source .agent/state/native-infra.env
./scripts/local/run-assistant-backend.sh
```

Then verify login with seeded user:

```sh
curl -sS -X POST http://localhost:8000/api/auth/login \
  -H 'content-type: application/json' \
  --data '{"email":"test.user@exobrain.local","password":"password123","session_mode":"web","issuance_policy":"session"}' \
  -c /tmp/exobrain.cookies

curl -sS http://localhost:8000/api/users/me -b /tmp/exobrain.cookies
```

## What the agent scripts do

- `native-infra-up.sh`
  - Starts Postgres, NATS, Qdrant with native processes.
  - Writes connection exports to `.agent/state/native-infra.env`.
- `native-infra-health.sh`
  - Checks Postgres readiness and HTTP health for NATS monitor/Qdrant.
- `assistant-db-setup-native.sh`
  - Applies assistant DB bootstrap, migrations, and seed data in native mode.
- `native-infra-down.sh`
  - Stops NATS/Qdrant started by agent scripts.
  - Stops local PGDATA-based Postgres instances; set `AGENT_STOP_SYSTEM_PG=1` to stop system cluster.

## Build/test loop

```sh
./scripts/local/build-assistant-backend.sh
./scripts/local/build-assistant-frontend.sh
./scripts/local/build-knowledge-interface.sh

cd apps/assistant-backend && uv run --with pytest --with pytest-asyncio pytest
cd apps/assistant-frontend && npm test
```

## Cleanup

```sh
./scripts/agent/native-infra-down.sh
```
