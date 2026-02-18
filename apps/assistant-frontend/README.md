# Exobrain Assistant Frontend

SvelteKit + Skeleton frontend for the Exobrain chatbot UI.

## Local build and run

From the repository root:

```bash
./scripts/local/build-assistant-frontend.sh
./scripts/local/run-assistant-frontend.sh
```

Notes:
- Re-run `build-assistant-frontend.sh` after changing frontend source.
- Dependency installation is skipped unless `node_modules` is missing or `package-lock.json` changed.


## Running unit tests

From `apps/assistant-frontend` run:

```bash
npm test
```

This runs the Vitest component suite for chat and authentication UI flows in a JSDOM environment.

## Local environment endpoints

### Application endpoint

- Assistant frontend UI: `http://localhost:5173`

### Upstream dependency endpoint

- Assistant backend API (default local run): `http://localhost:8000`

### Shared infrastructure endpoints

- PostgreSQL: `localhost:15432`
- Qdrant: `localhost:16333` (HTTP), `localhost:16334` (gRPC)
- Memgraph: `localhost:17687` (Bolt), `localhost:17444` (HTTP)
- NATS: `localhost:14222` (client), `localhost:18222` (monitoring)

## Kubernetes baseline

The project local cluster helper (`scripts/k3d-up.sh`) defaults to:

- Kubernetes image: `rancher/k3s:v1.35.1-k3s1`
- Local LoadBalancer mapping: `localhost:8080 -> :80`, `localhost:8443 -> :443`
- Ingress routing: `http://localhost:8080/` -> assistant frontend, `http://localhost:8080/api` -> assistant backend

## Known local dev caveat (Codex environment)

In this environment, `npm run dev` currently fails at runtime with:

- `TypeError: options.root.render is not a function`

Observed dependency mismatch behind this behavior:

- `@sveltejs/kit` `2.5.8`
- transitive `@sveltejs/vite-plugin-svelte` `3.1.2` / `svelte-hmr` `0.16.0`
- `svelte` `5.51.x`

Build (`npm run build`) and unit tests (`npm test`) still pass.
See `docs/codex-runbook.md` for remediation paths.

## API routing behavior

The frontend always calls `POST /api/chat/message`.

- **Local development (`npm run dev`)**: Vite proxies `/api/*` to `http://localhost:8000` by default. Override with `ASSISTANT_BACKEND_URL` if needed.
- **Cluster/nonlocal deployments**: the browser keeps calling relative `/api/*`; ingress routes these requests to the assistant backend service.
