# Architecture Intent (Working Context)

This document provides **non-binding context** for contributors and coding agents.
It helps task-level decisions stay aligned with long-term direction without over-scoping work.

## Long-term direction

Exobrain is evolving toward a self-improving assistant backed by a GraphRAG knowledge system:

- Knowledge graph for entities/relationships and contextual structure.
- Vector storage for semantic retrieval over conversations and artifacts.
- Pipelines that extract, update, and reconcile user-relevant knowledge from assistant interactions.

## Current-state guardrail

Treat implementation in repository code as authoritative over aspirational ideas.
When in conflict, prefer current code/contracts and leave intent docs updated as needed.

## Domain concepts to preserve

- **Provenance**: track where knowledge came from.
- **Temporal context**: represent when facts were true/observed.
- **Confidence**: distinguish facts, hypotheses, and uncertain inferences.
- **Conflict handling**: allow contradictory claims with source/time-aware reconciliation.

## Near-term non-goals

- Do not introduce broad platform redesigns in feature-level PRs.
- Do not over-generalize schemas/interfaces before concrete requirements.
- Do not assume always-on external infra in local/cloud-agent workflows.

## How to use this doc in PRs

Use this context to justify small, incremental decisions (naming, data shape, boundaries).
If a change materially affects the concepts above, add a brief note in PR description.
