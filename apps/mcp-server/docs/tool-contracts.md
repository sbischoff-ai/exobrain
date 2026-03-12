# MCP Server Tool Contracts

This document is the canonical human-readable reference for all tool contracts exposed by `apps/mcp-server`.

For the strict typed source of truth, see:

- `app/contracts/tools.py`
- `app/adapters/*_registry_builder.py`

## Discovery and invocation envelopes

### List tools

`GET /mcp/tools`

Response:

- `tools`: array of tool metadata
  - `name`: tool identifier
  - `description`: human-readable behavior summary
  - `inputSchema`: JSON Schema object for `arguments`

### Invoke tool

`POST /mcp/tools/invoke`

Request body:

- `name` (string, required): tool identifier
- `arguments` (object, required): tool-specific payload
- `metadata` (object, optional)
  - `correlation_id` (string | null)
  - `request_id` (string | null)

Success response body:

- `ok`: `true`
- `name`: invoked tool name
- `result`: tool-specific output payload
- `metadata`: echoed metadata when provided

Error response body:

- `ok`: `false`
- `name`: invoked tool name
- `error`
  - `code`: machine-readable error code
  - `message`: human-readable message
- `metadata`: echoed metadata when provided

---

## Utility tools

### `echo`

Description: Return the input text.

**Input (`arguments`)**

- `text` (string, required): minimum length `1`

**Output (`result`)**

- `text` (string)

### `add`

Description: Add two integers.

**Input (`arguments`)**

- `a` (integer, required)
- `b` (integer, required)

**Output (`result`)**

- `sum` (integer): `a + b`

---

## Web tools

### `web_search`

Description: Search the web for candidate sources and return normalized title/url/snippet metadata.

**Input (`arguments`)**

- `query` (string, required): minimum length `1`
- `max_results` (integer, optional, default `5`): range `1..10`
- `recency_days` (integer | null, optional): minimum `1`
- `include_domains` (array of strings | null, optional)
- `exclude_domains` (array of strings | null, optional)

**Output (`result`)**

- `results` (array)
  - `title` (string)
  - `url` (string)
  - `snippet` (string)
  - `score` (number | null)
  - `published_at` (string | null)

### `web_fetch`

Description: Fetch readable plaintext from a URL and return normalized content metadata.

**Input (`arguments`)**

- `url` (string, required): minimum length `1`
- `max_chars` (integer, optional, default `4000`): range `100..20000`

**Output (`result`)**

- `url` (string)
- `title` (string | null)
- `content_text` (string)
- `extracted_at` (string | null)
- `content_truncated` (boolean)

---

## Knowledge tools

### `resolve_entities`

Description: Resolve input entities against the knowledge graph and create missing entities when intent indicates creation.

> Current implementation returns deterministic placeholder resolution data in local/test flows while deeper integration is pending.

**Input (`arguments`)**

- `entities` (array, required): minimum length `1`
  - `name` (string, required): minimum length `1`
  - `type_hint` (string | null, optional): maximum length `120`
  - `description_hint` (string | null, optional): maximum length `300`
  - `expected_existence` (enum, optional, default `"unknown"`)
    - `"new"`
    - `"existing"`
    - `"unknown"`

**Output (`result`)**

- `results` (array)
  - `entity_id` (string)
  - `name` (string)
  - `aliases` (array of strings)
  - `entity_type` (string)
  - `description` (string)
  - `status` (enum)
    - `"matched"`
    - `"created"`
    - `"unresolved"`
  - `confidence` (number): range `0.0..1.0`
  - `newly_created` (boolean)

---


### `get_entity_context`

Description: Fetch markdown context for a canonical entity and return adjacent entities for graph-aware follow-up lookups. Related entities are collected from top-level KI neighbors and block-level neighbors, then deduplicated by canonical neighbor entity id.

**Input (`arguments`)**

- `entity_id` (string, required): minimum length `1`
- `depth` (integer | null, optional): range `0..32`; maps to knowledge `max_block_level` (default `3` when omitted, and clamped to `32` before KI RPC)
- `focus` (string | null, optional): maximum length `160`

**Output (`result`)**

- `context_markdown` (string): compact markdown summary, including context snippets and `@entity_id` handles for related entities
- `related_entities` (array; resolve-compatible fields only)
  - `entity_id` (string): from neighbor `other_entity.id`
  - `name` (string): from neighbor `other_entity.name`
  - `aliases` (array of strings): from neighbor `other_entity.aliases`
  - `entity_type` (string): type name resolved via KI `GetSchema` (without setting optional `universe_id`) from neighbor `other_entity.type_id`; falls back to raw `type_id` (or `"unknown"`) when schema mapping is unavailable
  - `description` (string): from neighbor `other_entity.description`; falls back to concise `Related entity <name-or-id>` when omitted

`related_entities` intentionally follows the `resolve_entities` result schema subset so agents can recursively fetch deeper context without shape conversion.

#### Chaining pattern: `resolve_entities -> get_entity_context`

Use `resolve_entities` to canonicalize user-provided entity names, then pass the resolved `entity_id` to `get_entity_context`.

1. Call `resolve_entities` with user input.
2. Select rows where `status` is `"matched"` or `"created"`.
3. Call `get_entity_context` for each selected `entity_id`.
4. Optionally recurse on returned `related_entities` (same field shape as resolve output subset).

Example:

`resolve_entities` request:

```json
{
  "name": "resolve_entities",
  "arguments": {
    "entities": [
      {
        "name": "Ada Lovelace",
        "type_hint": "person",
        "expected_existence": "existing"
      }
    ]
  }
}
```

`resolve_entities` response excerpt:

```json
{
  "ok": true,
  "name": "resolve_entities",
  "result": {
    "results": [
      {
        "entity_id": "ent_ada_lovelace",
        "name": "Ada Lovelace",
        "aliases": ["Augusta Ada King"],
        "entity_type": "person",
        "description": "Early computing pioneer",
        "status": "matched",
        "confidence": 0.97,
        "newly_created": false
      }
    ]
  }
}
```

`get_entity_context` request:

```json
{
  "name": "get_entity_context",
  "arguments": {
    "entity_id": "ent_ada_lovelace",
    "depth": 2,
    "focus": "programming contributions"
  }
}
```

`get_entity_context` response excerpt:

```json
{
  "ok": true,
  "name": "get_entity_context",
  "result": {
    "context_markdown": "# Ada Lovelace\n...",
    "related_entities": [
      {
        "entity_id": "ent_charles_babbage",
        "name": "Charles Babbage",
        "aliases": [],
        "entity_type": "person",
        "description": "Related entity Charles Babbage"
      }
    ]
  }
}
```

---


## Agent self-descriptive metadata contract

Tool discovery metadata is a hard contract for autonomous agents that must choose and invoke tools without human help.

- Every tool in `GET /mcp/tools` must include a non-empty, meaningful top-level `description`.
- Critical arguments in `inputSchema.properties` must include field-level `description` text with enough context for safe use (at minimum for web tools and `resolve_entities`).
- Descriptions should communicate intent and constraints (for example purpose, limits, freshness, or matching hints), not just restate field names.

## Notes on strictness and compatibility

- All request/response models are strict (`extra="forbid"`), so unknown fields are rejected.
- Tool discovery schemas use `inputSchema` (camelCase) in response metadata.
- Registry-level feature flags and dependency gates can make specific tools unavailable at runtime even when documented here.
