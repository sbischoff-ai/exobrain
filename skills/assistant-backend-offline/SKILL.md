# assistant-backend-offline

## Use this skill when

- Task touches `apps/assistant-backend` chat/auth/journal flow.
- You need backend behavior in Codex/cloud-agent environments without OpenAI/Tavily network dependencies.
- You need deterministic local responses via mock message files.

## Canonical references

- [`docs/agents/codex-runbook.agent.md`](../../docs/agents/codex-runbook.agent.md)
- [`AGENTS.md`](../../AGENTS.md)

## Command sequence (exact repo scripts)

1. Start native infra:

```sh
./scripts/agent/native-infra-up.sh
./scripts/agent/native-infra-health.sh
```

2. Initialize assistant DB (bootstrap + migrations + seeds):

```sh
./scripts/agent/assistant-db-setup-native.sh
```

3. Start backend in offline mode (mock agent + mock web tools):

```sh
./scripts/agent/run-assistant-backend-offline.sh
```

4. Verify seeded login/session:

```sh
curl -sS -X POST http://localhost:8000/api/auth/login \
  -H 'content-type: application/json' \
  --data '{"email":"test.user@exobrain.local","password":"password123","session_mode":"web","issuance_policy":"session"}' \
  -c /tmp/exobrain.cookies

curl -sS http://localhost:8000/api/users/me -b /tmp/exobrain.cookies
```

5. Optional backend unit-test loop (prefer project `.venv` interpreter):

```sh
cd apps/assistant-backend
uv sync --extra dev
uv run python -m pytest -m "not integration"
```

## Failure handling

- **`reshape: command not found`**
  - Confirm tool availability: `reshape --help`.
  - If missing in the environment, stop and document blocker; do not attempt internet-based install as default flow.
- **Python/pyenv mismatch (`python3` resolves to 3.10, import/runtime errors)**
  - Use:
    - `cd apps/assistant-backend`
    - `uv sync --extra dev`
    - `uv run python -m pytest ...`
- **Qdrant missing/unreachable**
  - Check health: `./scripts/agent/native-infra-health.sh`.
  - If binary is missing, script logs `qdrant not found; skipping`; continue only if current backend task does not depend on Qdrant paths.
- **Seed/migration failures**
  - Re-run from clean state:

```sh
./scripts/agent/native-infra-down.sh
./scripts/agent/native-infra-up.sh
./scripts/agent/assistant-db-setup-native.sh
```

## Expected verification output

- `native-infra-up.sh` prints: `native infra startup attempted` and env file path.
- `native-infra-health.sh` prints `postgres: ok`, plus `qdrant`/`nats monitor` statuses.
- `assistant-db-setup-native.sh` ends with: `assistant_db initialized, reshaped, and seeded`.
- Login verification returns user JSON for `test.user@exobrain.local`.

## Rollback / cleanup

```sh
./scripts/agent/native-infra-down.sh
rm -f /tmp/exobrain.cookies
```
