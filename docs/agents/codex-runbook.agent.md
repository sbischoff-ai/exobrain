---
audience: agent
status: active
---

# Codex Runbook (Cloud Agent)

Use this runbook when Docker/k3d flows are unavailable.

## Choose your workflow in 30 seconds

| Task type | Required services | Skill to invoke | Script entrypoint | Verification command |
| --- | --- | --- | --- | --- |
| Backend-only bugfix | Postgres, NATS, Qdrant | None (default agent workflow) | `./scripts/agent/assistant-offline-up.sh` then `./scripts/agent/run-assistant-backend-offline.sh` | `cd apps/assistant-backend && uv run python -m pytest -m "not integration"` |
| Frontend UI tweak | None (mock API mode) | None (default agent workflow) | `./scripts/agent/run-assistant-frontend-mock.sh` | `cd apps/assistant-frontend && npm test` |
| Frontend E2E validation | None (mock API mode) | None (default agent workflow) | `./scripts/agent/run-assistant-frontend-e2e.sh` | `./scripts/agent/run-assistant-frontend-e2e.sh` |
| DB migration/schema changes | Postgres | None (default agent workflow) | `./scripts/agent/assistant-db-setup-native.sh` | `./scripts/agent/assistant-db-setup-native.sh` |
| Knowledge-interface ingestion changes | Postgres, NATS, Qdrant | None (default agent workflow) | `./scripts/agent/native-infra-up.sh` then `./scripts/local/run-knowledge-interface.sh` | `./scripts/agent/native-infra-health.sh` |
| Docs-only changes | None | None (default agent workflow) | N/A | `pnpm -s prettier --check docs/agents/codex-runbook.agent.md AGENTS.md` |

Use this matrix to pick the fastest path; detailed instructions remain in the sections below.

## Quick start (tested)

```sh
./scripts/agent/assistant-offline-up.sh
./scripts/agent/run-assistant-backend-offline.sh
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

cd apps/assistant-backend && uv sync --extra dev && uv run python -m pytest -m "not integration"
cd apps/assistant-frontend && npm test
```

## Cleanup

```sh
./scripts/agent/native-infra-down.sh
```

## Mock chat responses for offline/backend testing

When `MAIN_AGENT_USE_MOCK=true`, assistant-backend reads responses from `MAIN_AGENT_MOCK_MESSAGES_FILE` (default: `apps/assistant-backend/mock-data/main-agent-messages.md`).

Format responses in markdown and separate each message with:

```text
--- message
```

The mock model cycles through these messages and wraps to the first one when it reaches the end.


## Assistant-backend integration API tests

Run against any reachable backend URL (native local process or k3d ingress):

```sh
cd apps/assistant-backend
cp tests/integration/.env.integration.example tests/integration/.env.integration
# update ASSISTANT_BACKEND_BASE_URL in the env file as needed
ASSISTANT_BACKEND_INTEGRATION_ENV_FILE=tests/integration/.env.integration \
  uv run --with pytest --with pytest-asyncio --with httpx pytest -m integration
```

The suite expects assistant seed user credentials:
- `test.user@exobrain.local` / `password123`


### Python interpreter note for Codex containers

Some containers expose `python3` from a pyenv shim (for example 3.10) even when `/usr/bin/python3.12` is installed.
Use `uv sync --extra dev` and run tests via `uv run python -m pytest` from `apps/assistant-backend` to force the project `.venv` interpreter and avoid version mismatch errors (for example `datetime.UTC` import failures).


## Frontend-only exploration (no backend)

Run the frontend in mock API mode to bypass backend startup entirely:

```sh
./scripts/agent/run-assistant-frontend-mock.sh
```

Then open `http://localhost:5173` and login with:
- email: `test.user@exobrain.local`
- password: `password123`

This mode supports intro/login, journal sidebar interactions, streaming chat UX states, and logout/session flows using in-memory fixture data.

## Full offline integration (frontend + backend + local infra)

Use two terminals:

```sh
# terminal A
./scripts/agent/assistant-offline-up.sh
./scripts/agent/run-assistant-backend-offline.sh

# terminal B
./scripts/local/run-assistant-frontend.sh
```

This keeps backend auth/journal/chat APIs real while replacing OpenAI/Tavily calls with local mocks (`MAIN_AGENT_USE_MOCK=true`, `WEB_TOOLS_USE_MOCK=true`).


## Frontend E2E suite (Playwright)

Run end-to-end coverage against mock API mode (recommended for agent workflows):

```sh
./scripts/agent/run-assistant-frontend-e2e.sh
```

Script behavior:
- Uses `npm ci` when `e2e/package-lock.json` is present (falls back to `npm install` only when no lockfile exists).
- Reuses a valid `e2e/node_modules` install by default for faster reruns.
- Reinstalls deps when `e2e/node_modules` is missing/invalid, or when forced via `--force-reinstall` or `E2E_FORCE_REINSTALL=true`.
- Prints whether `E2E_USE_EXISTING_SERVER=true` is active before the test run.
- Exits non-zero with concise hints for common failures (dependency install issues or missing Playwright browsers).

Useful flags/env:

```sh
# force reinstall deps before running tests
E2E_FORCE_REINSTALL=true ./scripts/agent/run-assistant-frontend-e2e.sh
# or
./scripts/agent/run-assistant-frontend-e2e.sh --force-reinstall

# run tests against an already running frontend server
E2E_USE_EXISTING_SERVER=true ./scripts/agent/run-assistant-frontend-e2e.sh
```

Manual flow (if you already have frontend running):

```sh
cd e2e
E2E_USE_EXISTING_SERVER=true npm test
```
