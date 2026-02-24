# Knowledge Graph Schema (System-wide)

This document defines the shared world-model schema used across Exobrain services.

## Core concept

- Entities are lightweight world objects (`Entity` + sublabels).
- Blocks are the narrative surface (`Block` nodes with text).
- Each entity has a single root block (`DESCRIBED_BY`).
- Root blocks can fan out into deeper details (`SUMMARIZES`) as a DAG.
- Blocks cross-link entities (`MENTIONS`) to support retrieval + backlinks.

## Entity-to-block structure

```mermaid
flowchart TD
  U[Universe]
  E[Entity]
  B0[Root Block]
  B1[Detail Block A]
  B2[Detail Block B]
  X[Another Entity]

  E -- IS_PART_OF --> U
  E -- DESCRIBED_BY --> B0
  B0 -- SUMMARIZES --> B1
  B0 -- SUMMARIZES --> B2
  B1 -- MENTIONS --> X
```

## Invariants

- Every `Entity` has exactly one `IS_PART_OF` edge to `Universe`.
- Every `Entity` has exactly one `DESCRIBED_BY` root block.
- `SUMMARIZES` forms a DAG (no cycles).
- World semantics should prefer explicit edge types over excess properties.

## Starter node labels

- `Universe`
- `Entity` (+ starter sublabels like `Person`, `Group`, `Institution`, `Place`, `Object`, `Concept`, `Species`, `Event`, `Task`)
- `Block` (+ optional `Quote`, `Image`)

## Starter edge set

- Scoping/content: `IS_PART_OF`, `DESCRIBED_BY`, `SUMMARIZES`, `MENTIONS`
- General fallback: `RELATED_TO`
- Spatial/containment: `AT`, `LIES_IN`, `CONTAINS`
- Social: `KNOWS`, `MEMBER_OF`, `AFFILIATED_WITH`
- Event/task: `PARTICIPATED_IN`, `INVOLVES`, `BEFORE`, `CAUSES`, `ASSIGNED_TO`, `DONE_FOR`, `DEPENDS_ON`
- Classification/identity: `ABOUT`, `INSTANCE_OF`, `ALSO_KNOWN_AS`, `SAME_AS`

## Trust metadata

Edges may include:
- `confidence: float`
- `status: asserted | disputed | falsified`
- `context: string`

Blocks may include editorial trust hints:
- `confidence`
- `status`

## Vector store representation (Qdrant)

`Block` nodes are embedded into a `blocks` collection. The graph remains source-of-truth.

```mermaid
flowchart LR
  MG[Memgraph Block node] --> EMB[Embedding model]
  EMB --> Q[(Qdrant blocks collection)]
  MG --> META[Payload metadata\nuniverse_id/root_entity_id/entity_ids]
  META --> Q
```

Required payload fields:
- `block_id`, `universe_id`, `text`, `root_entity_id`, `entity_ids`

## Universe semantics

- Universe membership is primarily a filtering/context mechanism.
- Entity/Block IDs are expected to be globally unique across universes.
- Cross-universe edges are valid and can encode semantic links between real-world concepts and fictional instances.
- Intended modeling pattern: a real-world `Entity:Concept` (for example, Darth Vader as a character concept) may connect via `INSTANCE_OF` to a fictional-universe `Entity:Person`.

## Label fields in ingestion payloads

- `labels` exist on ingestion payloads for forward compatibility with richer label-aware graph writes.
- Current implementation does not project payload labels into dynamic Memgraph labels yet; writes currently use stable base labels (`Entity`, `Block`).
