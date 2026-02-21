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
- **PostgreSQL metastore**
  - Assistant state and relational metadata.
- **Memgraph**
  - Graph-oriented knowledge representation.
- **Qdrant**
  - Vector storage and semantic retrieval indexes.
- **NATS**
  - Event-oriented coordination for asynchronous workflows.

## Integration boundaries

- Frontend uses backend HTTP APIs (`/api/*`).
- Backend may call knowledge-interface over gRPC for retrieval/update use cases.
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
