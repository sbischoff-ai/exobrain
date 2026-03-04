from __future__ import annotations

import asyncio
import logging
import sys

from app.contracts import JobEnvelope
from app.worker.job_registry import JOB_MODULE_BY_TYPE

logger = logging.getLogger(__name__)


class LocalProcessWorkerRunner:
    """Run each job in its own python process by module script."""

    @staticmethod
    def _log_subprocess_output(
        output: bytes,
        *,
        source: str,
        job: JobEnvelope,
        worker_module: str,
        log_level: int,
    ) -> None:
        text = output.decode("utf-8", errors="replace").strip()
        if not text:
            return

        for line in text.splitlines():
            logger.log(
                log_level,
                "worker subprocess %s: %s",
                source,
                line,
                extra={
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                    "worker_module": worker_module,
                },
            )

    async def run_job(self, job: JobEnvelope) -> None:
        module_name = JOB_MODULE_BY_TYPE.get(job.job_type)
        if module_name is None:
            raise ValueError(f"no worker module configured for job type '{job.job_type}'")

        logger.debug("launching worker subprocess", extra={"job_id": job.job_id, "worker_module": module_name})
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            module_name,
            "--job-envelope",
            job.model_dump_json(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        self._log_subprocess_output(
            stdout,
            source="stdout",
            job=job,
            worker_module=module_name,
            log_level=logging.INFO,
        )
        self._log_subprocess_output(
            stderr,
            source="stderr",
            job=job,
            worker_module=module_name,
            log_level=logging.WARNING if process.returncode == 0 else logging.ERROR,
        )

        if process.returncode != 0:
            err = stderr.decode("utf-8").strip()
            raise RuntimeError(err or f"worker module failed for {job.job_type}")

        logger.debug("worker subprocess succeeded", extra={"job_id": job.job_id, "worker_module": module_name})
