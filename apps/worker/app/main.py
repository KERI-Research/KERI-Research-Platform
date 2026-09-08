"""FastAPI app for the ORAMA synthetic research worker."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Annotated
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse

from app.pipeline.evaluate import feasibility_decision
from app.pipeline.ingest import (
    DatasetIngestionError,
    dataset_from_storage,
    dataset_to_frames,
)
from app.pipeline.models import train_comparison_models
from app.pipeline.reporting import (
    build_markdown_report,
    build_report_payload,
    render_html_report,
    render_model_card,
)
from app.pipeline.validation import SchemaValidationError, validate_frames
from app.schemas import (
    DatasetValidationRequest,
    JobRequest,
    JobResult,
    JobStatus,
    JobStatusResponse,
    StoragePresignDownloadRequest,
    StoragePresignRequest,
)
from app.security import verify_shared_secret
from app.storage import (
    delete_object,
    delete_prefix,
    download_bytes,
    generate_presigned_download_url,
    generate_presigned_upload_url,
    key_exists,
    upload_bytes,
    validate_object_key,
)
from app.store import InMemoryJobStore

logger = logging.getLogger(__name__)
app = FastAPI(
    title="ORAMA Worker",
    version="0.1.0",
    description=(
        "Synthetic-only research worker for longitudinal feasibility modelling. "
        "Non-diagnostic and not clinically validated."
    ),
)
job_store = InMemoryJobStore()


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Redirect root to /health so HF Space probes and browsers get a 200."""
    return RedirectResponse(url="/health")


@app.get("/health")
def health() -> dict[str, str]:
    """Return a minimal unauthenticated health status."""
    return {"status": "ok"}


def _upload_key(upload_id: str, filename: str) -> str:
    safe_filename = re.sub(
        r"[^A-Za-z0-9._-]",
        "_",
        filename.rsplit("/", maxsplit=1)[-1].rsplit("\\", maxsplit=1)[-1],
    )
    if not safe_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename does not contain usable characters.",
        )
    return f"uploads/{upload_id}/{safe_filename}"


def _result_key(job_id: str, prefix: str, filename: str) -> str:
    normalized_prefix = prefix.strip("/")
    if normalized_prefix != f"results/{job_id}":
        raise ValueError(
            "Result artifacts must use the deterministic job result prefix."
        )
    validate_object_key(normalized_prefix)
    return validate_object_key(f"{normalized_prefix}/{filename}")


def _dataset_for_request(request: JobRequest):
    if request.dataset is not None:
        return request.dataset
    if not request.dataset_object_key or not request.dataset_filename:
        raise DatasetIngestionError(
            "Provide either an inline dataset or a private dataset object key and filename."
        )
    return _dataset_from_private_object(
        request.dataset_object_key, request.dataset_filename
    )


def _dataset_from_private_object(dataset_object_key: str, dataset_filename: str):
    object_key = validate_object_key(dataset_object_key)
    if not object_key.startswith("uploads/"):
        raise DatasetIngestionError("Dataset object must be a private upload.")
    return dataset_from_storage(
        object_key, download_bytes(object_key), dataset_filename
    )


@app.post("/internal/storage/presign-upload")
def presign_upload(
    request: StoragePresignRequest,
    _: Annotated[None, Depends(verify_shared_secret)],
) -> dict[str, str]:
    """Issue a narrowly scoped R2 PUT URL without exposing storage credentials."""

    key = _upload_key(request.upload_id, request.filename)
    return {
        "object_key": key,
        "upload_url": generate_presigned_upload_url(key, request.content_type),
    }


@app.get("/internal/storage/uploads/{upload_id}/exists")
def uploaded_object_exists(
    upload_id: str,
    filename: str,
    _: Annotated[None, Depends(verify_shared_secret)],
) -> dict[str, bool | str]:
    """Confirm that the exact object represented by an upload session exists."""

    key = _upload_key(upload_id, filename)
    return {"object_key": key, "exists": key_exists(key)}


@app.post("/internal/storage/presign-download")
def presign_download(
    request: StoragePresignDownloadRequest,
    _: Annotated[None, Depends(verify_shared_secret)],
) -> dict[str, str]:
    """Issue a short-lived read URL for an artifact, never for a raw upload."""

    object_key = validate_object_key(request.object_key)
    if not object_key.startswith("results/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only result artifacts can be downloaded.",
        )
    return {
        "object_key": object_key,
        "download_url": generate_presigned_download_url(object_key),
    }


@app.delete("/internal/storage/uploads/{upload_id}")
def delete_uploaded_object(
    upload_id: str,
    filename: str,
    _: Annotated[None, Depends(verify_shared_secret)],
) -> dict[str, str]:
    """Delete one raw upload after the web retention policy authorizes it."""

    object_key = _upload_key(upload_id, filename)
    delete_object(object_key)
    return {"object_key": object_key, "status": "deleted"}


@app.delete("/internal/storage/jobs/{job_id}/artifacts")
def delete_job_artifacts(
    job_id: str,
    _: Annotated[None, Depends(verify_shared_secret)],
) -> dict[str, int | str]:
    """Delete only artifacts inside the job's deterministic result prefix."""

    result_prefix = validate_object_key(f"results/{job_id}")
    return {"prefix": result_prefix, "deleted_count": delete_prefix(result_prefix)}


@app.post("/internal/datasets/validate")
def validate_stored_dataset(
    request: DatasetValidationRequest,
    _: Annotated[None, Depends(verify_shared_secret)],
) -> dict[str, object]:
    """Validate a private upload without returning row-level data to the caller."""

    try:
        dataset = _dataset_from_private_object(
            request.dataset_object_key,
            request.dataset_filename,
        )
        frames = dataset_to_frames(dataset)
        validate_frames(frames)
    except (DatasetIngestionError, SchemaValidationError, ValueError) as exc:
        return {
            "status": "FAILED",
            "summary": {},
            "errors": [{"code": "SCHEMA-001", "message": str(exc)}],
            "warnings": [],
        }

    return {
        "status": "READY",
        "summary": {
            "participants": len(frames["participants"]),
            "observations": len(frames["observations"]),
            "outcomes": len(frames["outcomes"]),
            "encounters": len(frames["encounters"]),
            "data_dictionary": len(frames["data_dictionary"]),
        },
        "errors": [],
        "warnings": [],
    }


def _run_pipeline(request: JobRequest) -> JobResult:
    frames = dataset_to_frames(_dataset_for_request(request))
    validate_frames(frames)

    horizon_results, exclusions_by_horizon, cohort_size_by_horizon, feature_manifest = (
        train_comparison_models(
            participants=frames["participants"],
            observations=frames["observations"],
            outcomes=frames["outcomes"],
            encounters=frames["encounters"],
            data_dictionary=frames["data_dictionary"],
            horizons=request.analysis_config.horizons,
            prediction_gap_days=request.analysis_config.prediction_gap_days,
            min_history_days=request.analysis_config.min_history_days,
            min_observations_per_variable=request.analysis_config.min_observations_per_variable,
            random_state=request.analysis_config.random_state,
            test_size=request.analysis_config.test_size,
        )
    )
    decision = feasibility_decision(horizon_results)
    report_json = build_report_payload(
        job_id=request.job_id,
        dataset_id=request.dataset_id,
        config=request.analysis_config,
        cohort_size_by_horizon=cohort_size_by_horizon,
        exclusions_by_horizon=exclusions_by_horizon,
        horizon_results=horizon_results,
        feasibility=decision.conclusion,
        decision_reasons=decision.reasons,
        feature_manifest=feature_manifest,
    )
    if request.config_hash and report_json["configuration_hash"] != request.config_hash:
        raise ValueError(
            "Worker configuration hash does not match the locked job configuration."
        )
    report_markdown = build_markdown_report(report_json)
    report_references = ["inline:report_json", "inline:report_markdown"]
    if request.result_write_prefix:
        report_json_key = _result_key(
            request.job_id, request.result_write_prefix, "report.json"
        )
        report_markdown_key = _result_key(
            request.job_id, request.result_write_prefix, "report.md"
        )
        report_html_key = _result_key(
            request.job_id, request.result_write_prefix, "report.html"
        )
        model_card_key = _result_key(
            request.job_id, request.result_write_prefix, "model-card.md"
        )
        upload_bytes(
            report_json_key,
            json.dumps(report_json, indent=2).encode("utf-8"),
            "application/json",
        )
        upload_bytes(
            report_markdown_key,
            report_markdown.encode("utf-8"),
            "text/markdown; charset=utf-8",
        )
        upload_bytes(
            report_html_key,
            render_html_report(report_json).encode("utf-8"),
            "text/html; charset=utf-8",
        )
        upload_bytes(
            model_card_key,
            render_model_card(report_json).encode("utf-8"),
            "text/markdown; charset=utf-8",
        )
        report_references = [
            f"storage:{report_json_key}",
            f"storage:{report_markdown_key}",
            f"storage:{report_html_key}",
            f"storage:{model_card_key}",
        ]

    return JobResult(
        feasibility_conclusion=decision.conclusion,
        decision_reasons=decision.reasons,
        metrics_by_horizon=horizon_results,
        report_json=report_json,
        report_markdown=report_markdown,
        report_references=report_references,
    )


def _callback_is_allowed(callback_url: str) -> bool:
    configured_app_url = os.getenv("ORAMA_VERCEL_URL", "").rstrip("/")
    if not configured_app_url:
        return False

    candidate = urlparse(callback_url)
    configured = urlparse(configured_app_url)
    return (
        candidate.scheme == configured.scheme
        and candidate.netloc == configured.netloc
        and candidate.path.startswith("/api/orama/jobs/")
        and candidate.path.endswith("/callback")
    )


def _notify_callback(request: JobRequest, job: JobStatusResponse) -> None:
    if not request.callback_url:
        return
    if not _callback_is_allowed(request.callback_url):
        logger.warning(
            "Skipping callback for job_id=%s because its URL is not an approved ORAMA origin.",
            request.job_id,
        )
        return

    secret = os.getenv("ORAMA_WORKER_SHARED_SECRET")
    if not secret:
        logger.error(
            "Skipping callback for job_id=%s because the worker shared secret is unavailable.",
            request.job_id,
        )
        return

    payload = {
        "status": job.status.value,
        "worker_result": job.result.model_dump(mode="json") if job.result else None,
        "error_message": job.error,
    }
    try:
        callback_request = Request(
            request.callback_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Orama-Worker-Secret": secret,
            },
            method="POST",
        )
        with urlopen(callback_request, timeout=10) as response:
            if response.status >= 400:
                logger.warning(
                    "Worker callback returned HTTP %s for job_id=%s.",
                    response.status,
                    request.job_id,
                )
    except (OSError, URLError, ValueError) as exc:
        logger.warning("Worker callback failed for job_id=%s: %s", request.job_id, exc)


def _execute_job(request: JobRequest) -> None:
    job_store.transition(
        request.job_id,
        JobStatus.RUNNING,
        message="Research analysis pipeline started.",
    )
    try:
        result = _run_pipeline(request)
        final_status = (
            JobStatus.NOT_EVALUABLE
            if result.feasibility_conclusion.value == "NOT_EVALUABLE"
            else JobStatus.SUCCEEDED
        )
        job = job_store.transition(
            request.job_id,
            final_status,
            message="Research analysis pipeline completed.",
            result=result,
        )
    except (DatasetIngestionError, SchemaValidationError, ValueError) as exc:
        job = job_store.transition(
            request.job_id,
            JobStatus.FAILED,
            message="Input dataset validation failed.",
            error=str(exc),
        )
    except Exception:
        logger.exception(
            "Unhandled worker pipeline failure for job_id=%s", request.job_id
        )
        job = job_store.transition(
            request.job_id,
            JobStatus.FAILED,
            message="Unhandled pipeline failure.",
            error="Pipeline execution failed. Inspect server logs for details.",
        )

    _notify_callback(request, job)


@app.post("/internal/jobs/run", response_model=JobStatusResponse)
def run_job(
    request: JobRequest,
    background_tasks: BackgroundTasks,
    _: Annotated[None, Depends(verify_shared_secret)],
) -> JobStatusResponse:
    """Queue a locked research job and return immediately for status polling."""

    if not request.analysis_config.analysis_locked:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Analysis configuration must be locked before held-out evaluation.",
        )

    existing = job_store.get(request.job_id)
    if existing and existing.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
        return existing

    queued = job_store.create_or_reset(
        request.job_id, message="Job accepted by worker."
    )
    background_tasks.add_task(_execute_job, request)
    return queued


@app.get("/internal/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: str,
    _: Annotated[None, Depends(verify_shared_secret)],
) -> JobStatusResponse:
    """Return stored job status and result payload when present."""

    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )
    return job
