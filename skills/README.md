# Skills Index

Use this directory as a quick router to workflow-specific runbooks. Keep detailed behavior in each `SKILL.md` and link back to canonical docs to avoid drift.

## Which skill to use when

- **`assistant-backend-offline`**: Use when tasks touch `apps/assistant-backend` auth/chat/journal APIs and should run without external model/tool dependencies.
- **`assistant-frontend-mock`**: Use when tasks touch `apps/assistant-frontend` UX and you want fast UI iteration against mock API responses.
- **`knowledge-interface-local`**: Use when tasks touch `apps/knowledge-interface`, graph ingestion, Memgraph/Qdrant integration, or schema-driven knowledge workflows.
- **`docs-update`**: Use when tasks are documentation-first and need consistent updates across `README`, `docs/`, and agent guidance references.

## Canonical references

- Agent runbook: [`docs/agents/codex-runbook.agent.md`](../docs/agents/codex-runbook.agent.md)
- Repository agent policy: [`AGENTS.md`](../AGENTS.md)
