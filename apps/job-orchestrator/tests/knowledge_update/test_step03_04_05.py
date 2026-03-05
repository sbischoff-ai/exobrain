from __future__ import annotations

import pytest

from app.worker.jobs.knowledge_update import _classify_candidate_matches, _extract_matched_entity_id


def test_step03_classify_candidate_matches_uses_thresholds() -> None:
    assert _classify_candidate_matches([])["status"] == "new_entity"
    strong_match = _classify_candidate_matches([{"entity_id": "entity-1", "score": 0.61}])
    assert strong_match["status"] == "matched"


def test_step05_extract_matched_entity_id_parses_expected_decisions() -> None:
    assert _extract_matched_entity_id("MATCH(entity-1)") == "entity-1"
    assert _extract_matched_entity_id("NEW_ENTITY") is None
    assert _extract_matched_entity_id("unknown") is None
