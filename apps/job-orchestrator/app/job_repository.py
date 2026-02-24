from __future__ import annotations

import json

from app.contracts import JobEnvelope
from app.database import Database


class JobRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    async def register_requested(self, job: JobEnvelope) -> bool:
        status = await self._db.fetchrow(
            """
            INSERT INTO orchestrator_jobs (job_id, job_type, correlation_id, payload, attempt, status)
            VALUES ($1, $2, $3, $4::jsonb, $5, 'requested')
            ON CONFLICT (job_id) DO NOTHING
            RETURNING job_id
            """,
            job.job_id,
            job.job_type,
            job.correlation_id,
            json.dumps(job.payload),
            job.attempt,
        )
        return status is not None

    async def mark_processing(self, job_id: str, attempt: int) -> None:
        await self._db.execute(
            """
            UPDATE orchestrator_jobs
            SET status = 'processing', attempt = $2, updated_at = NOW()
            WHERE job_id = $1
            """,
            job_id,
            attempt,
        )

    async def mark_completed(self, job_id: str) -> None:
        await self._db.execute(
            """
            UPDATE orchestrator_jobs
            SET status = 'completed', completed_at = NOW(), updated_at = NOW()
            WHERE job_id = $1
            """,
            job_id,
        )

    async def mark_failed(self, job_id: str, error_message: str) -> None:
        await self._db.execute(
            """
            UPDATE orchestrator_jobs
            SET status = 'failed', last_error = $2, updated_at = NOW()
            WHERE job_id = $1
            """,
            job_id,
            error_message,
        )
