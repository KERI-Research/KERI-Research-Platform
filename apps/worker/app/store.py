"""Thread-safe in-memory job store for the synthetic worker scaffold."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock

from app.schemas import (
    JobProgress,
    JobResult,
    JobStateTransition,
    JobStatus,
    JobStatusResponse,
)


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
            progress=JobProgress(percent=0, phase="queued", detail=message),
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

    def update_progress(
        self, job_id: str, percent: int, phase: str, detail: str | None = None
    ) -> JobStatusResponse | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            record.progress = JobProgress(
                percent=percent,
                phase=phase,
                detail=detail,
            )
            record.updated_at = now
            return deepcopy(record)

    def get(self, job_id: str) -> JobStatusResponse | None:
        with self._lock:
            record = self._jobs.get(job_id)
            return deepcopy(record) if record is not None else None

    def list(self) -> list[JobStatusResponse]:
        with self._lock:
            return [deepcopy(record) for record in self._jobs.values()]
