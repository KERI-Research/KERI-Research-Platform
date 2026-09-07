"""FastAPI app for the ORAMA synthetic research worker."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status

from app.pipeline.evaluate import feasibility_conclusion
from app.pipeline.ingest import dataset_to_frames
from app.pipeline.models import train_comparison_models
from app.pipeline.reporting import build_markdown_report, build_report_payload
from app.pipeline.validation import SchemaValidationError, validate_frames
from app.schemas import JobRequest, JobResult, JobStatus, JobStatusResponse
from app.security import verify_shared_secret
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


@app.get("/health")
def health() -> dict[str, str]:
    """Return a minimal unauthenticated health status."""

    return {"status": "ok"}


def _run_pipeline(request: JobRequest) -> JobResult:
    frames = dataset_to_frames(request.dataset)
    validate_frames(frames)

    horizon_results, exclusions_by_horizon, cohort_size_by_horizon, feature_manifest = train_comparison_models(
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
    feasibility = feasibility_conclusion(horizon_results)
    report_json = build_report_payload(
        job_id=request.job_id,
        config=request.analysis_config,
        cohort_size_by_horizon=cohort_size_by_horizon,
        exclusions_by_horizon=exclusions_by_horizon,
        horizon_results=horizon_results,
        feasibility=feasibility,
        feature_manifest=feature_manifest,
    )
    report_markdown = build_markdown_report(report_json)
    return JobResult(
        feasibility_conclusion=feasibility,
        metrics_by_horizon=horizon_results,
        report_json=report_json,
        report_markdown=report_markdown,
        report_references=["inline:report_json", "inline:report_markdown"],
    )


@app.post("/internal/jobs/run", response_model=JobStatusResponse)
def run_job(
    request: JobRequest,
    _: Annotated[None, Depends(verify_shared_secret)],
) -> JobStatusResponse:
    """Run the synthetic research pipeline synchronously while recording realistic status transitions."""

    job_store.create_or_reset(request.job_id, message="Job accepted by worker.")
    job_store.transition(request.job_id, JobStatus.RUNNING, message="Synthetic analysis pipeline started.")
    try:
        result = _run_pipeline(request)
        final_status = JobStatus.NOT_EVALUABLE if result.feasibility_conclusion.value == "NOT_EVALUABLE" else JobStatus.SUCCEEDED
        return job_store.transition(
            request.job_id,
            final_status,
            message="Synthetic analysis pipeline completed.",
            result=result,
        )
    except SchemaValidationError as exc:
        return job_store.transition(
            request.job_id,
            JobStatus.FAILED,
            message="Input schema validation failed.",
            error=str(exc),
        )
    except Exception as exc:
        logger.exception("Unhandled worker pipeline failure for job_id=%s", request.job_id)
        return job_store.transition(
            request.job_id,
            JobStatus.FAILED,
            message="Unhandled pipeline failure.",
            error="Pipeline execution failed. Inspect server logs for details.",
        )


@app.get("/internal/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: str,
    _: Annotated[None, Depends(verify_shared_secret)],
) -> JobStatusResponse:
    """Return stored job status and result payload when present."""

    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job
