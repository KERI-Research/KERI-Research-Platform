"""Typed request, response, and domain models for the ORAMA worker."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    horizons: list[int] = Field(default_factory=lambda: [30, 90, 180, 365, 730])
    min_history_days: int = 365
    min_observations_per_variable: int = 2
    prediction_gap_days: int = 0
    test_size: float = 0.25
    random_state: int = 42


class JobRequest(StrictModel):
    job_id: str
    dataset: DatasetPayload
    analysis_config: AnalysisConfig = Field(default_factory=AnalysisConfig)


class FeasibilityConclusion(str, Enum):
    GO = "GO"
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
