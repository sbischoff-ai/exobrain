# Architecture Overview

## Why this exists

This document gives a stable, high-level map of Exobrain runtime components and their responsibilities.

## Scope

- Cross-service architecture only.
- No step-by-step local setup procedures (those live in `docs/development/`).
- No implementation history (that lives in `docs/operations/major-changes.md`).

## System components

- **assistant-frontend** (`apps/assistant-frontend`)
  - Browser UI and session-aware chat/journal interactions.
- **assistant-backend** (`apps/assistant-backend`)
  - HTTP APIs for auth, chat, journals, and message history.
  - Coordinates domain services and persistence boundaries.
  - Runs a LangGraph-based assistant agent with pluggable tools (`app/agents/tools`), including web research wrappers (`web_search`, `web_fetch`).
- **knowledge-interface** (`apps/knowledge-interface`)
  - gRPC boundary for retrieval and knowledge update workflows.
- **job-orchestrator** (`apps/job-orchestrator`)
  - Asynchronous job orchestrator/worker consuming NATS subjects and persisting job state.
- **mcp-server** (`apps/mcp-server`)
  - Dedicated MCP tool runtime exposing typed tool discovery and invocation endpoints.
  - Owns the canonical MCP HTTP contract and tool catalog metadata served to assistant-backend.
- **PostgreSQL metastore**
  - Assistant state and relational metadata.
- **Memgraph**
  - Graph-oriented knowledge representation.
- **Qdrant**
  - Vector storage and semantic retrieval indexes.
- **NATS**
  - Event-oriented coordination for asynchronous workflows.

## Integration boundaries

### Protocol boundary map

- Frontend -> assistant-backend: HTTP REST (`/api/*`).
- assistant-backend -> knowledge-interface: gRPC.
- assistant-backend -> mcp-server: HTTP REST (`GET /mcp/tools`, `POST /mcp/tools/invoke`), not JSON-RPC.
- assistant-backend -> job-orchestrator: gRPC (`EnqueueJob`), with downstream worker execution over NATS/JetStream.
- job-orchestrator workers -> external stores: PostgreSQL/Memgraph/Qdrant adapters as needed by job type.

### MCP tool catalog ownership

- `apps/mcp-server` owns the tool catalog exposed by `GET /mcp/tools`, including tool names, descriptions, and input JSON schemas.
- `apps/assistant-backend` consumes that catalog at runtime and should not define a parallel source of truth for MCP tool schemas.
- Canonical schema/module path: `apps/mcp-server/app/contracts/` (especially `tools.py` for invocation/list envelopes).

### Data boundaries

- Backend persists assistant domain state in PostgreSQL.
- Knowledge workflows may rely on Memgraph and Qdrant.

## Service layering notes

Assistant backend and frontend are expected to keep clear layering boundaries:

- Backend routers delegate to domain services (not direct DB calls from route handlers).
- Frontend route components remain UI-focused and call services/stores for business/persistence logic.

Detailed engineering rules live in [`../standards/engineering-standards.md`](../standards/engineering-standards.md).

## References

- Docs hub: [`../README.md`](../README.md)
- Architecture intent: [`architecture-intent.md`](architecture-intent.md)
- Engineering standards: [`../standards/engineering-standards.md`](../standards/engineering-standards.md)
