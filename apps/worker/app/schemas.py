"""Typed request, response, and domain models for the ORAMA worker."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model that rejects unexpected fields."""

    model_config = ConfigDict(extra="forbid")


class Participant(StrictModel):
    patient_id: str
    sex: str | None = None
    age: float | None = None
    diagnosis_date: datetime | None = None
    reference_date: datetime | None = None
    cohort_label: str | None = None


class Observation(StrictModel):
    patient_id: str
    variable_code: str
    value: float
    observed_at: datetime
    unit: str | None = None


class Outcome(StrictModel):
    patient_id: str
    outcome_code: str
    outcome_at: datetime
    label: int = 1


class Encounter(StrictModel):
    patient_id: str
    encountered_at: datetime
    encounter_type: str | None = None


class DataDictionaryEntry(StrictModel):
    variable_code: str
    display_name: str | None = None
    unit: str | None = None
    domain: str | None = None
    is_treatment_related: bool = False
    is_outcome_derived: bool = False
    is_post_index_only: bool = False


class DatasetPayload(StrictModel):
    participants: list[Participant] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    outcomes: list[Outcome] = Field(default_factory=list)
    encounters: list[Encounter] = Field(default_factory=list)
    data_dictionary: list[DataDictionaryEntry] = Field(default_factory=list)


class AnalysisConfig(StrictModel):
    horizons: list[Annotated[int, Field(gt=0, le=3650)]] = Field(
        default_factory=lambda: [30, 90, 180, 365, 730]
    )
    min_history_days: int = Field(default=365, ge=0, le=3650)
    min_observations_per_variable: int = Field(default=2, ge=1, le=100)
    prediction_gap_days: int = Field(default=0, ge=0, le=3650)
    test_size: float = Field(default=0.25, gt=0, lt=0.5)
    random_state: int = Field(default=42, ge=0)
    analysis_locked: bool = False


class StoragePresignRequest(StrictModel):
    upload_id: str = Field(min_length=1, max_length=200)
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=255)


class StoragePresignDownloadRequest(StrictModel):
    object_key: str = Field(min_length=1, max_length=1024)


class DatasetValidationRequest(StrictModel):
    dataset_object_key: str = Field(min_length=1, max_length=1024)
    dataset_filename: str = Field(min_length=1, max_length=255)


class JobRequest(StrictModel):
    job_id: str
    dataset_id: str | None = Field(default=None, max_length=255)
    dataset: DatasetPayload | None = None
    dataset_object_key: str | None = Field(default=None, max_length=1024)
    dataset_filename: str | None = Field(default=None, max_length=255)
    result_write_prefix: str | None = Field(default=None, max_length=1024)
    callback_url: str | None = Field(default=None, max_length=2048)
    config_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    analysis_config: AnalysisConfig = Field(default_factory=AnalysisConfig)

    @model_validator(mode="after")
    def validate_dataset_source(self) -> "JobRequest":
        has_inline_dataset = self.dataset is not None
        has_storage_dataset = bool(self.dataset_object_key or self.dataset_filename)
        if has_inline_dataset == has_storage_dataset:
            raise ValueError(
                "Provide exactly one dataset source: inline dataset or private object key and filename."
            )
        if has_storage_dataset and not (
            self.dataset_object_key and self.dataset_filename
        ):
            raise ValueError(
                "Private storage jobs require both dataset_object_key and dataset_filename."
            )
        return self


class FeasibilityConclusion(str, Enum):
    GO_FOR_EXTERNAL_VALIDATION = "GO_FOR_EXTERNAL_VALIDATION"
    NO_GO = "NO_GO"
    REDIRECT = "REDIRECT"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class JobStateTransition(StrictModel):
    status: JobStatus
    at: datetime
    message: str | None = None


class JobResult(StrictModel):
    feasibility_conclusion: FeasibilityConclusion
    decision_reasons: list[str] = Field(default_factory=list)
    metrics_by_horizon: dict[str, Any]
    report_json: dict[str, Any]
    report_markdown: str
    report_references: list[str] = Field(default_factory=list)


class JobStatusResponse(StrictModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    status_history: list[JobStateTransition] = Field(default_factory=list)
    result: JobResult | None = None
    error: str | None = None
