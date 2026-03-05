from __future__ import annotations

from app.settings import Settings
from app.worker.jobs.knowledge_update import core


def build_json_schema() -> dict[str, object]:
    return core._build_step_ten_mentions_schema()


async def run(merged_graph_delta: dict[str, object], settings: Settings, requesting_user_id: str) -> dict[str, object]:
    return await core._run_step_ten_finalize_graph_delta(merged_graph_delta, settings, requesting_user_id)
