# Knowledge Interface gRPC API and Graph Delta Contract

This document describes what clients must send to `UpsertGraphDelta` and
`InitializeUserGraph`, plus how to query `FindEntityCandidates`.

## Core rule

A graph delta is accepted only when it is schema-valid:

- node and edge types must exist in the canonical schema
- node/edge properties must exist on the type or inherited parent type
- edge endpoints must match one of the schema edge rules

Validation is split into:

- **request payload rules** (type/property/rule checks on records supplied in the request)
- **target graph state rules** (relationship cardinality checks against the graph state after applying the upsert)

This means block updates can rely on existing `DESCRIBED_BY`/`SUMMARIZES` parent edges already present in the graph; those edges do not need to be resubmitted unless they are changing.

## ID format requirements

Client-provided IDs are **domain IDs**, not Memgraph-internal IDs.

- IDs must be RFC 4122 UUID strings
- Example: `550e8400-e29b-41d4-a716-446655440000`
- Examples:
  - `550e8400-e29b-41d4-a716-446655440001`
  - `550e8400-e29b-41d4-a716-446655440002`

Invalid IDs return `InvalidArgument` with detailed messages.

## Type mapping

Request now includes `universes[]` (id + name) at the top level; `universe_id`/`universe_name` are no longer root fields.
`UpsertGraphDeltaRequest` has no root-level `user_id` or `visibility`; those are provided per universe/entity/block/edge record.
Entities may omit `universe_id`, in which case the service defaults to the Real World universe (`9d7f0fa5-78c1-4805-9efb-3f8f16090d7f`).
This implicit universe assignment also satisfies the `IS_PART_OF` relationship rule during validation.


Clients provide `type_id` (for example `node.person` or `node.block`).
The server resolves and writes the full label chain from schema inheritance (for example `:Entity:Person:Friend`).

## Required/allowed properties

Properties are checked against schema property definitions including inheritance.
Global `node`/`edge` property definitions also apply to every node/edge subtype without duplicating definitions per concrete type.

Example:

- `node.person` inherits `node.entity`
- if `node.entity` defines `name`, then `node.person` can use `name`
- if `edge` defines `confidence`/`status`/`context`, then every edge type (for example `RELATED_TO`, `LOCATED_AT`) must provide them

## Edge endpoint validation

Edges are validated with schema rules (`knowledge_graph_schema_edge_rules`).

For example, a `RELATED_TO` edge is valid only if a matching rule exists for source and target node types (or their ancestors).

- For `PRIVATE` edge writes, endpoint nodes may be either `PRIVATE` or `SHARED`; caller services enforce RBAC/user boundaries.
- `UpsertGraphDelta` may include mixed-user node/edge records in a single request; ownership policies are enforced by upstream caller services.

```mermaid
flowchart LR
  A[node.person]
  B[node.person]
  A -->|edge.related_to| B
```

## Qdrant projection contract

Qdrant stores a projection of all `node.block` nodes.

- point id = block id
- payload includes `block_id`, `universe_id`, `root_entity_id`, `user_id`, `visibility`, `text`, `block_level`
- updating a block rewrites the corresponding point (new embedding + payload)

## Transaction behavior

Writes are coordinated across Memgraph and Qdrant:

1. Memgraph transaction starts
2. Delta is written to Memgraph transaction
3. Qdrant upserts are applied
4. Memgraph transaction commits

Failure behavior:

- If steps 1-3 fail: Memgraph is rolled back
- If step 4 fails: newly upserted Qdrant points are deleted as compensation

## Example `UpsertGraphDelta` payload shape

Minimal valid delta for one person + one block + explicit edges:

- `entities[0].id = 550e8400-e29b-41d4-a716-446655440001`
- `entities[0].type_id = node.person`
- `entities[0].properties` contains `name`
- `blocks[0].id = 550e8400-e29b-41d4-a716-446655440002`
- `blocks[0].type_id = node.block`
- `blocks[0].properties` contains `text`
- `edges[0].edge_type = DESCRIBED_BY` (for entity -> block relationship)
- `SUMMARIZES` edges can target new blocks from existing parent blocks; root metadata resolves from the existing parent chain.
- `edges[1].edge_type = RELATED_TO` (optional semantic edge)

For interactive request prototyping use `grpcui -plaintext localhost:50051`.


Visibility values are accepted as provided per node/edge; scope is carried per universe/entity/block/edge (no top-level request scope fields).

## FindEntityCandidates

`FindEntityCandidates` returns candidate entities by combining lexical name matching and
semantic similarity over `node.block` text.

### Request schema

- `names[]`: free-form candidate names (case-insensitive; trimmed and normalized)
- `potential_type_ids[]`: optional entity type filter (`node.person`, `node.company`, ...)
- `short_description`: optional semantic hint text (embedded and searched against Qdrant)
- `user_id`: required requester scope
- `limit`: optional maximum result count

At least one non-empty `names[]` value or a non-empty `short_description` is required.

### Response schema

Each `EntityCandidate` includes:

- `entity_id`
- `entity_name`
- `described_by_text` (best available lowest block-level description, if present)
- `score` (combined lexical + semantic ranking score)
- `matched_name` / `matched_alias` (best-effort matched tokens)
- `entity_type_id`

### Matching semantics

- Name score is computed from normalized `names[]` against entity `name` and `aliases`.
- Semantic score comes from Qdrant block similarity and is weighted by block depth:
  - `weighted = raw_similarity * (1 / (1 + block_level))`
  - root description blocks (`block_level = 0`) contribute most.
- Entity hits are deduplicated by `entity_id` across lexical and semantic paths.
- Final score is combined as:
  - `0.55 * name_score + 0.45 * weighted_semantic_score`
- Results are sorted descending by final score and truncated by `limit` when provided.
