from __future__ import annotations

from pydantic import BaseModel

from app.contracts import KnowledgeUpdatePayload

JOB_MODULE_BY_TYPE: dict[str, str] = {
    "knowledge.update": "app.worker.jobs.knowledge_update",
}

JOB_PAYLOAD_MODEL_BY_TYPE: dict[str, type[BaseModel]] = {
    "knowledge.update": KnowledgeUpdatePayload,
}
