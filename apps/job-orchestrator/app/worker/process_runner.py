from __future__ import annotations

import asyncio
import json
import sys

from app.contracts import JobEnvelope
from app.worker.job_registry import JOB_MODULE_BY_TYPE


class LocalProcessWorkerRunner:
    """Run each job in its own python process by module script."""

    async def run_job(self, job: JobEnvelope) -> None:
        module_name = JOB_MODULE_BY_TYPE.get(job.job_type)
        if module_name is None:
            raise ValueError(f"no worker module configured for job type '{job.job_type}'")

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            module_name,
            "--job-envelope",
            job.model_dump_json(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            err = stderr.decode("utf-8").strip()
            raise RuntimeError(err or f"worker module failed for {job.job_type}")
