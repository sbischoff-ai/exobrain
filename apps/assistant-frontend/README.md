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


## Frontend architecture conventions

For repository-wide layering standards, use [`docs/standards/engineering-standards.md`](../../docs/standards/engineering-standards.md).

Frontend-specific structure in this app:

- `src/lib/models/`: shared domain and API data contracts.
- `src/lib/services/`: API adapters and business workflows.
- `src/lib/stores/`: local state persistence helpers.
- `src/lib/utils/`: reusable helper utilities.

## Logging

Frontend logging is implemented through a small console logger wrapper (`src/lib/utils/logging.ts`) with environment-aware defaults:

- Local dev (`npm run dev`): default level is `debug`.
- Non-local/prod builds (Docker/Kubernetes): default level is `warn`.
- Override with `PUBLIC_LOG_LEVEL` (`debug`, `info`, `warn`, `error`).

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

## API routing behavior

The frontend always calls `POST /api/chat/message`.

- **Local development (`npm run dev`)**: Vite proxies `/api/*` to `http://localhost:8000` by default. Override with `ASSISTANT_BACKEND_URL` if needed.
- **Cluster/nonlocal deployments**: the browser keeps calling relative `/api/*`; ingress routes these requests to the assistant backend service.

## Authentication + journal session behavior

- The app now opens on an intro/login screen when there is no active backend session.
- On successful login (cookie-backed web session), the main assistant workspace is shown. Logging out clears local sessionStorage state and returns to the intro screen.
- The workspace stores user identity, current journal reference, and journal messages (including per-message client ids) in `sessionStorage` under `exobrain.assistant.session`.
- On page load, the client re-syncs stored journal state by comparing stored message count with `/api/journal/{reference}` `message_count`; mismatches trigger a refetch of only the latest 50 messages.
- The frontend stores backend `message_count` in session state and increments it client-side as chat messages are added, so pagination controls remain consistent between syncs.
- Message APIs return newest-first (`sequence` descending) for cursor paging; the frontend reorders each page to chronological display and prepends older pages via a "Load older messages" control when total count exceeds 50.
- Chat view preserves bottom-oriented reading by auto-scrolling on every message update, including each streamed assistant chunk update.
- If no stored state exists, the client initializes state from `/api/journal/today?create=true` and `/api/journal/today/messages`.
- The journal sidebar is collapsed by default and allows switching between journal references. Only today's journal keeps chat input enabled.

- Chat requests use the backend idempotency contract and send `client_message_id` with each `/api/chat/message` request.


## Related docs

- Repository docs hub: [`../../docs/README.md`](../../docs/README.md)
- Local setup workflow: [`../../docs/development/local-setup.md`](../../docs/development/local-setup.md)
- Engineering standards: [`../../docs/standards/engineering-standards.md`](../../docs/standards/engineering-standards.md)
