from __future__ import annotations

from app.adapters.entity_context_markdown_formatter import MAX_MARKDOWN_CHARS, render_entity_context_markdown
from app.contracts import GetEntityContextRelatedEntityItem


def _related(
    *,
    entity_id: str,
    name: str,
) -> GetEntityContextRelatedEntityItem:
    return GetEntityContextRelatedEntityItem(
        entity_id=entity_id,
        name=name,
        aliases=[],
        entity_type="node.person",
        description="",
    )


def test_render_entity_context_markdown_orders_context_and_related_deterministically() -> None:
    response = {
        "entity": {"id": "ent_ada", "name": "Ada Lovelace", "type_id": "node.person", "aliases": ["Ada"]},
        "blocks": [
            {"id": "blk-z", "name": "Sibling Z", "block_level": 2, "text": "z text"},
            {"id": "blk-a", "name": "Root", "block_level": 0, "text": "root text"},
            {"id": "blk-b", "name": "Nested B", "block_level": 1, "text": "nested b text"},
            {"id": "blk-c", "name": "Nested A", "block_level": 1, "text": "nested a text"},
        ],
    }

    markdown = render_entity_context_markdown(
        response=response,
        related_entities=[
            _related(entity_id="ent_b", name="Beta"),
            _related(entity_id="ent_a", name="Alpha"),
        ],
        focus="ignore me",
    )

    assert markdown == (
        "## Ada Lovelace\n"
        "- Type: `node.person`\n"
        "- Aliases: Ada\n\n"
        "### Context\n"
        "- root text\n"
        "- nested b text\n"
        "- nested a text\n"
        "- z text\n\n"
        "### Related\n"
        "- @ent_a: Alpha\n"
        "- @ent_b: Beta"
    )


def test_render_entity_context_markdown_omits_empty_sections_and_handles_missing_data() -> None:
    markdown = render_entity_context_markdown(
        response={"entity": {}, "blocks": [{"text": "   "}, {"not_text": "x"}]},
        related_entities=[],
    )

    assert markdown == ""


def test_render_entity_context_markdown_enforces_compact_size_caps() -> None:
    long_text = "x" * 600
    response = {
        "entity": {"id": "ent_long", "name": "Long Entity", "description": "d" * 500},
        "blocks": [
            {"id": f"blk-{index:02d}", "block_level": index % 3, "text": long_text}
            for index in range(30)
        ],
    }
    related_entities = [
        _related(entity_id=f"ent_{index:02d}", name=f"Name {index}")
        for index in range(20)
    ]

    markdown = render_entity_context_markdown(response=response, related_entities=related_entities)

    assert len(markdown) <= MAX_MARKDOWN_CHARS
    assert markdown.count("\n- @") <= 6
    assert markdown.count("\n- x") <= 12
