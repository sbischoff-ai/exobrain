# Engineering Standards

## Why this exists

This document defines cross-service engineering standards for Exobrain application code and API-facing behavior.

## Scope

- Standards for assistant frontend, assistant backend, and their API contracts.
- High-level rules that stay stable across feature iterations.
- Implementation details for one-off changes should stay in code or PRs, not here.

## Backend service and API standards

- Keep FastAPI route handlers thin and delegate behavior to domain services.
- Keep persistence access behind service boundaries; avoid direct database access in routers.
- Use explicit, typed request/response models and concise API descriptions.
- Prefer additive, backward-compatible API changes unless a breaking change is intentionally planned.

## Frontend architecture standards

- Keep route components focused on UI composition and interaction flow.
- Put API calls and business logic in `src/lib/services`.
- Put persistence/session mechanics in `src/lib/stores`.
- Keep shared payload/domain contracts in `src/lib/models`.

## Contract and pagination standards

- API list endpoints must document sort order and cursor semantics clearly.
- If responses are newest-first for efficient pagination, client code should normalize display order where chronological UX is expected.
- Cursor fields should be stable, deterministic, and scoped to the resource being paged.

## Database migration standards

- Use Reshape migrations as the canonical schema change workflow for assistant metastore.
- Migration files should be additive where possible and include deterministic backfill logic when introducing derived/order fields.
- Keep migration docs procedural and reusable; avoid recording one-time migration implementation details as enduring standards.

## Operational checklist

Before merging changes that touch API/domain behavior:

1. Verify route-to-service boundaries remain intact.
2. Verify frontend layering boundaries remain intact.
3. Update relevant README/docs links when contracts or workflows change.
4. Run app-level tests relevant to touched services.

## References

- Docs hub: [`../README.md`](../README.md)
- Architecture overview: [`../architecture/architecture-overview.md`](../architecture/architecture-overview.md)
- Documentation standards: [`documentation-standards.md`](documentation-standards.md)
- Assistant backend README: [`../../apps/assistant-backend/README.md`](../../apps/assistant-backend/README.md)
- Assistant frontend README: [`../../apps/assistant-frontend/README.md`](../../apps/assistant-frontend/README.md)
