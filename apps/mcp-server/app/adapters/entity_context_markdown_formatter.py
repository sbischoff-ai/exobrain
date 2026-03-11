from __future__ import annotations

from typing import Any

from app.contracts import GetEntityContextRelatedEntityItem

MAX_MARKDOWN_CHARS = 3000
_MAX_HEADER_CHARS = 700
_MAX_CONTEXT_CHARS = 1700
_MAX_NEIGHBOR_CHARS = 800
_MAX_CONTEXT_ITEMS = 12
_MAX_NEIGHBOR_ITEMS = 6
_MAX_LINE_CHARS = 260


def render_entity_context_markdown(
    *,
    response: dict[str, Any],
    related_entities: list[GetEntityContextRelatedEntityItem],
    focus: str | None = None,
) -> str:
    _ = focus  # reserved for future LLM-guided focusing step

    entity = response.get("entity") if isinstance(response.get("entity"), dict) else {}

    sections: list[str] = []

    header_section = _build_header_section(entity)
    if header_section:
        sections.append(_truncate_text(header_section, _MAX_HEADER_CHARS))

    context_section = _build_context_section(response)
    if context_section:
        sections.append(_truncate_text(context_section, _MAX_CONTEXT_CHARS))

    neighbor_section = _build_neighbor_section(related_entities)
    if neighbor_section:
        sections.append(_truncate_text(neighbor_section, _MAX_NEIGHBOR_CHARS))

    return _truncate_text("\n\n".join(sections), MAX_MARKDOWN_CHARS)


def _build_header_section(entity: dict[str, Any]) -> str:
    entity_name = _coerce_text(entity.get("name")) or _coerce_text(entity.get("id"))
    if not entity_name:
        return ""

    lines = [f"## {entity_name}"]

    entity_type = _coerce_text(entity.get("type_id"))
    if entity_type:
        lines.append(f"- Type: `{entity_type}`")

    aliases = _coerce_list(entity.get("aliases"))
    if aliases:
        lines.append(f"- Aliases: {', '.join(aliases)}")

    description = _coerce_text(entity.get("description"))
    if description:
        lines.append(f"- Summary: {_truncate_text(' '.join(description.split()), _MAX_LINE_CHARS)}")

    return "\n".join(lines)


def _build_context_section(response: dict[str, Any]) -> str:
    blocks = response.get("blocks") if isinstance(response.get("blocks"), list) else []

    normalized_blocks: list[tuple[tuple[int, str, str, int], str]] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue

        text = _coerce_text(block.get("text"))
        if not text:
            continue

        normalized_text = _truncate_text(" ".join(text.split()), _MAX_LINE_CHARS)
        block_level = _coerce_int(block.get("block_level"))
        if block_level is None or block_level < 0:
            block_level = 0

        block_id = _coerce_text(block.get("id")) or ""
        block_name = _coerce_text(block.get("name")) or ""

        normalized_blocks.append(((block_level, block_id, block_name, index), normalized_text))

    if not normalized_blocks:
        return ""

    normalized_blocks.sort(key=lambda item: item[0])

    lines = ["### Context"]
    for _, text in normalized_blocks[:_MAX_CONTEXT_ITEMS]:
        lines.append(f"- {text}")

    return "\n".join(lines)


def _build_neighbor_section(related_entities: list[GetEntityContextRelatedEntityItem]) -> str:
    if not related_entities:
        return ""

    sorted_related = sorted(
        related_entities,
        key=lambda item: (item.entity_id.lower(), item.name.lower(), item.relationship_type.lower()),
    )

    lines = ["### Related"]
    for related in sorted_related[:_MAX_NEIGHBOR_ITEMS]:
        line = f"- @{related.entity_id}: {related.name} ({related.relationship_type})"
        lines.append(_truncate_text(line, _MAX_LINE_CHARS))

    return "\n".join(lines)


def _truncate_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    if max_chars <= 1:
        return value[:max_chars]
    return value[: max_chars - 1].rstrip() + "…"


def _coerce_text(value: Any) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _coerce_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = _coerce_text(item)
        if text:
            items.append(text)
    return items


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None
