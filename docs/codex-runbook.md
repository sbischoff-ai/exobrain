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

## Known caveats observed in this environment

- The assistant frontend dev server can return HTTP 500 with:
  - `TypeError: options.root.render is not a function`

### Frontend mismatch details

The current dependency set mixes an older SvelteKit/Vite plugin chain with stable Svelte 5:

- `@sveltejs/kit` `2.5.8`
- `@sveltejs/vite-plugin-svelte` `3.1.2` (transitive from Kit)
- `svelte-hmr` `0.16.0` (transitive from plugin `3.1.2`, peer `svelte ^3 || ^4`)
- `svelte` `5.51.2`

This compiles and passes Vitest in this repo, but breaks SSR rendering in `npm run dev`.

### What to provide in the environment

Either of these consistent stacks will unblock frontend dev smoke tests:

1. **Keep current Kit/Vite generation, downgrade Svelte to 4.x**
   - good when you want minimal repo change risk
2. **Upgrade the Kit/plugin toolchain to a Svelte-5-native stack**
   - Kit version that supports modern `@sveltejs/vite-plugin-svelte` (v5/v6)
   - plugin/version set aligned with the installed Vite major

Until one of those stacks is applied consistently, treat frontend `npm run dev` smoke tests as unreliable in this environment.

## Cleanup

```sh
./scripts/agent/native-infra-down.sh
```
