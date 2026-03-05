from __future__ import annotations

import json


def build_step_two_entity_extraction_system_prompt(entity_schema_context: dict[str, object]) -> str:
    return "\n\n".join(
        [
            "You are the knowledge.update entity extraction worker.",
            (
                "Extract named entities from the markdown batch document and map each entity to the most specific "
                "knowledge node type using the schema context."
            ),
            (
                "Return strict JSON only: extracted_entities and extracted_universes. "
                "Do not include markdown, prose, or extra fields."
            ),
            (
                "Universe handling: if an entity is fictional and no matching universe exists in context, add an "
                "entry to extracted_universes and reference it from extracted_entities[].universe_id when possible."
            ),
            "Entity extraction schema context (JSON):\n" + json.dumps(entity_schema_context, sort_keys=True),
        ]
    )
