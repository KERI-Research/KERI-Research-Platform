"""Thread-safe in-memory job store for the synthetic worker scaffold."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock

from app.schemas import JobResult, JobStateTransition, JobStatus, JobStatusResponse


class InMemoryJobStore:
    """Durable job store mock — replace with real persistence (e.g., Redis/DB) for production."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, JobStatusResponse] = {}

    def create_or_reset(
        self, job_id: str, message: str | None = None
    ) -> JobStatusResponse:
        now = datetime.now(timezone.utc)
        record = JobStatusResponse(
            job_id=job_id,
            status=JobStatus.QUEUED,
            created_at=now,
            updated_at=now,
            status_history=[
                JobStateTransition(status=JobStatus.QUEUED, at=now, message=message)
            ],
        )
        with self._lock:
            self._jobs[job_id] = record
        return deepcopy(record)

    def transition(
        self,
        job_id: str,
        status: JobStatus,
        *,
        message: str | None = None,
        result: JobResult | None = None,
        error: str | None = None,
    ) -> JobStatusResponse:
        now = datetime.now(timezone.utc)
        with self._lock:
            record = self._jobs[job_id]
            record.status = status
            record.updated_at = now
            record.status_history.append(
                JobStateTransition(status=status, at=now, message=message)
            )
            if result is not None:
                record.result = result
            record.error = error
            updated = deepcopy(record)
        return updated

    def get(self, job_id: str) -> JobStatusResponse | None:
        with self._lock:
            record = self._jobs.get(job_id)
            return deepcopy(record) if record is not None else None
