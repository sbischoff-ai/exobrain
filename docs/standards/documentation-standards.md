# Documentation Standards

This guide defines how documentation is organized across the repository so humans and coding agents can quickly find the right source of truth.

## Scope

- Applies repository-wide unless a subdirectory document defines stricter local conventions.
- Prioritizes low-friction maintenance, discoverability, and clear ownership of information.

## Documentation Types: Purpose and Audience

### `README.md` (root and folder-scoped)

**Purpose**

- Provide a quick reference to what exists in the directory.
- Explain setup/run/debug commands needed to start work quickly.
- Link to deeper architecture/policy documents instead of duplicating them.

**Audience**

- Primary: engineers onboarding to a service/folder.
- Secondary: operators and agents needing command-oriented context.

**Expected content style**

- Task-oriented and concise.
- Optimized for “what do I run next?” workflows.

### `docs/` wiki-style project documentation

**Purpose**

- Hold project-wide architecture, design rationale, standards, and cross-cutting guidance.
- Capture canonical policies that multiple services consume.

**Audience**

- Primary: maintainers and contributors making cross-service changes.
- Secondary: reviewers and agents validating conventions.

**Expected content style**

- Durable guidance with explicit assumptions, links, and decision context.
- Should be the source of truth for global standards.

### `AGENTS.md`

**Purpose**

- Provide operational context and constraints for coding agents.
- Document environment limitations, required workflows, and implementation guardrails.

**Audience**

- Primary: coding agents and automation workflows.
- Secondary: humans reviewing agent constraints and defaults.

**Expected content style**

- High-signal operational instructions.
- Focused on execution constraints, not broad architecture narratives.

## File Size Guidance

- Target maximum for most documentation files: **200–250 lines**.
- If a document grows beyond the target, split by topic and cross-link.
- **Root `README.md` exception policy**:
  - The root README may exceed 250 lines when needed to preserve first-run onboarding flow.
  - Even when over the target, avoid embedding deep policy content better kept in `docs/`.

## Workflow Documentation Placement Rules

Use these placement rules to avoid startup-command duplication:

- **Cross-service startup flows** belong in `docs/development/local-setup.md`.
- **Process-orchestration boundaries** (Docker Compose vs `mprocs` vs k3d/agent scripts) belong in `docs/development/process-orchestration.md`.
- **Service READMEs** should keep only service-specific configuration, tests, and troubleshooting; link to development workflow docs for startup sequences.
- **Metastore READMEs** (`infra/metastore/*/README.md`) should document schema/migration commands only.

Examples:

- ✅ Allowed: local full-stack run-profile commands in `docs/development/local-setup.md`.
- ✅ Allowed: environment variables unique to `apps/assistant-backend` in `apps/assistant-backend/README.md`.
- ❌ Avoid: repeating the full multi-service startup sequence in every service README.
- ❌ Avoid: copying migration commands from `infra/metastore/*/README.md` into unrelated architecture docs.

## Redundancy Policy

- Do not duplicate policy text across files unless there is a strong operational reason.
- Prefer brief summaries with links to canonical sections.
- When two docs must mention the same concept:
  - Keep one designated source of truth.
  - Add a short pointer in the secondary doc (1–3 lines).
  - Update links immediately when source locations change.

## Required Section Templates

Use the following baseline templates when creating or overhauling documents.

### Template: `README.md`

1. `# <Name>`
2. `## What this directory/service is`
3. `## Quick start` (setup + run)
4. `## Common commands`
5. `## Configuration` (env vars, ports, dependencies)
6. `## Troubleshooting` (optional but recommended)
7. `## Related docs` (links into `docs/` and relevant local docs)

### Template: `docs/*.md`

1. `# <Topic>`
2. `## Why this exists`
3. `## Scope`
4. `## Standard / Policy / Design`
5. `## Operational checklist` (if applicable)
6. `## References` (source-of-truth links and related docs)

### Template: `AGENTS.md`

1. `# AGENTS.md`
2. `## Purpose`
3. `## Environment notes` (tooling limits, startup assumptions)
4. `## Required workflows` (build/test/migration expectations)
5. `## Guardrails and conventions`
6. `## Change log notes for agents` (lessons learned; concise)

## Agent-Targeted Docs Naming and Tagging

For agent-focused documentation that is not `AGENTS.md`:

- Preferred filename pattern: `*.agent.md`
  - Example: `docs/testing-workflows.agent.md`
- Add front matter where practical:

```yaml
---
audience: agent
status: active
---
```

- Include a “Human summary” section near the top when the doc is likely to be read by humans.

## Ownership and Review Expectations

- Authors should update nearby READMEs and relevant `docs/` links in the same change.
- Reviewers should reject PRs that introduce substantial policy duplication.
- Agent instructions that change execution behavior should be reflected in `AGENTS.md` and linked from related runbooks when relevant.
