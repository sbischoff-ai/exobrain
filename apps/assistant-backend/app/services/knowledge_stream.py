from __future__ import annotations

import json
from typing import Literal, TypedDict


KnowledgeUpdateStreamEventType = Literal["status", "done"]


class KnowledgeUpdateStatusEventData(TypedDict):
    job_id: str
    state: str
    attempt: int
    detail: str
    terminal: bool
    emitted_at: str


class KnowledgeUpdateDoneEventData(TypedDict):
    job_id: str
    state: str
    terminal: bool


class KnowledgeUpdateStreamEvent(TypedDict):
    type: KnowledgeUpdateStreamEventType
    data: KnowledgeUpdateStatusEventData | KnowledgeUpdateDoneEventData


def encode_knowledge_sse_event(event: KnowledgeUpdateStreamEvent) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
