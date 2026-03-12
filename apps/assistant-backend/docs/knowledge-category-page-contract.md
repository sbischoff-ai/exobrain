# Knowledge category/page API contract (`/api/knowledge/category*`, `/api/knowledge/page/*`)

## Why this exists

This document defines the backend HTTP contract for browsing knowledge categories and pages. It keeps assistant-backend and assistant-frontend aligned on payload shape, pagination, and error behavior for the category/page experience.

## Scope

- `GET /api/knowledge/category`
- `GET /api/knowledge/category/{category_id}/pages`
- `GET /api/knowledge/page/{page_id}`

All endpoints require authenticated user context.

## Endpoint: `GET /api/knowledge/category`

Returns the category tree projected from `GetSchema` (`universe_id=wiki`), filtering to active node types (`kind=node`, id prefix `node.`), rooted at direct `node.entity` subtypes (excluding `node.block` and `node.universe`), with deterministic ordering by `display_name` then `category_id`.

### 200 response

```json
{
  "categories": [
    {
      "category_id": "node.root",
      "display_name": "Root",
      "sub_categories": [
        {
          "category_id": "node.child",
          "display_name": "Child",
          "sub_categories": []
        }
      ]
    }
  ]
}
```

### Error mapping

- `400`: invalid request to upstream (`INVALID_ARGUMENT`)
- `503`: upstream unavailable/timed out (`UNAVAILABLE`, `DEADLINE_EXCEEDED`)
- `502`: all other upstream failures

## Endpoint: `GET /api/knowledge/category/{category_id}/pages`

Returns page summaries for a category from `ListEntitiesByType`.

### Query params

- `page_size` (optional, int >= 1)
- `page_token` (optional, non-empty string)

### 200 response

```json
{
  "knowledge_pages": [
    {
      "id": "entity-1",
      "title": "Entity One",
      "summary": "Entity summary",
      "metadata": {
        "created_at": "",
        "updated_at": "2026-02-19T10:00:00Z"
      }
    }
  ],
  "page_size": 20,
  "next_page_token": "next-cursor",
  "total_count": 42
}
```

### Notes

- `knowledge_pages` contains compact page items with `id`, `title`, `summary`, and `metadata` only.
- `metadata.created_at` is currently empty when upstream list payloads omit creation timestamps.
- Pagination values are passthrough from request and upstream response.

### Error mapping

- `400`: invalid request (`INVALID_ARGUMENT`)
- `503`: upstream unavailable/timed out (`UNAVAILABLE`, `DEADLINE_EXCEEDED`)
- `502`: all other upstream failures

## Endpoint: `GET /api/knowledge/page/{page_id}`

Returns page detail from `GetEntityContext` (`max_block_level=2`) with canonical timestamps in `metadata` and filtered entity-type properties in `properties`.

### 200 response

```json
{
  "id": "entity-1",
  "category_id": "node.task",
  "title": "Entity One",
  "summary": "Root",
  "metadata": {
    "created_at": "2026-02-19T09:00:00Z",
    "updated_at": "2026-02-19T10:00:00Z"
  },
  "properties": {
    "status": "in_progress",
    "priority": "high"
  },
  "links": [
    {
      "page_id": "entity-2",
      "title": "Entity Two",
      "summary": "Linked summary"
    }
  ],
  "content_blocks": [{"block_id": "b1", "markdown": "Root"}, {"block_id": "b2", "markdown": "Child"}]
}
```

### Notes

- `category_id` is the entity node type id from `GetEntityContext.entity.type_id`; clients can map it through `GET /api/knowledge/category` to resolve breadcrumb ancestry.
- `summary` is sourced from the text of the direct `DESCRIBED_BY` block (root block at level 0).
- `metadata` contains only canonical timestamps (`created_at`, `updated_at`).
- `properties` contains entity-type-specific values from upstream `entity_properties`, excluding reserved/system keys (`created_at`, `updated_at`, `visibility`, `user_id`, `type_id`, `id`).
- `links` are mapped from neighbor entities.
- `content_blocks` is an ordered list of entity blocks; clients render each block independently.

### Error mapping

- `404`: page not found
- `403`: access denied
- `503`: upstream unavailable/timed out
- `502`: other upstream failures

## References

- Router: `apps/assistant-backend/app/api/routers/knowledge.py`
- Service mapping: `apps/assistant-backend/app/services/knowledge_service.py`
- Schemas: `apps/assistant-backend/app/api/schemas/knowledge.py`
