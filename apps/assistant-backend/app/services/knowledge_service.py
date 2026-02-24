from __future__ import annotations

from app.services.contracts import JournalServiceProtocol, JobPublisherProtocol


class KnowledgeService:
    def __init__(self, journal_service: JournalServiceProtocol, job_publisher: JobPublisherProtocol) -> None:
        self._journal_service = journal_service
        self._job_publisher = job_publisher

    async def enqueue_update_job(self, *, user_id: str, journal_reference: str) -> str:
        rows = await self._journal_service.list_messages(
            user_id=user_id,
            journal_reference=journal_reference,
            limit=500,
            before_sequence=None,
        )
        payload_messages = [
            {
                "role": row.get("role"),
                "content": row.get("content"),
                "sequence": row.get("sequence"),
                "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
            }
            for row in rows
        ]
        return await self._job_publisher.enqueue_job(
            job_type="knowledge.update",
            correlation_id=user_id,
            payload={
                "journal_reference": journal_reference,
                "messages": payload_messages,
                "requested_by_user_id": user_id,
            },
        )
