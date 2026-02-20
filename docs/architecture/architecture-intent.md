# Architecture Intent (Working Context)

## Why this exists

This document provides non-binding architecture direction so contributors can make local decisions that still align with long-term goals.

## Scope

- Long-term intent and conceptual guardrails.
- Not a replacement for code-level source of truth.
- Not a procedural setup guide.

## Long-term direction

Exobrain is evolving toward a self-improving assistant backed by a GraphRAG knowledge system:

- Knowledge graph for entities/relationships and contextual structure.
- Vector storage for semantic retrieval over conversations and artifacts.
- Pipelines that extract, update, and reconcile user-relevant knowledge from assistant interactions.

## Current-state guardrail

Treat repository code/contracts as authoritative over aspirational ideas.
When in conflict, prefer current implementation and update intent docs separately as needed.

## Domain concepts to preserve

- **Provenance**: track where knowledge came from.
- **Temporal context**: represent when facts were true/observed.
- **Confidence**: distinguish facts, hypotheses, and uncertain inferences.
- **Conflict handling**: allow contradictory claims with source/time-aware reconciliation.

## Near-term non-goals

- Broad platform redesigns in feature-level PRs.
- Premature over-generalization of schemas/interfaces.
- Assumptions of always-on external infra in local/cloud-agent workflows.

## References

- Architecture overview: [`architecture-overview.md`](architecture-overview.md)
- Engineering standards: [`../standards/engineering-standards.md`](../standards/engineering-standards.md)
- Docs hub: [`../README.md`](../README.md)
