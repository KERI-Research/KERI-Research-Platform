"""Dataset ingestion helpers for inline synthetic payloads."""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel

from app.schemas import DatasetPayload


PARTICIPANT_COLUMNS = ["patient_id", "sex", "age", "diagnosis_date", "reference_date", "cohort_label"]
OBSERVATION_COLUMNS = ["patient_id", "variable_code", "value", "observed_at", "unit"]
OUTCOME_COLUMNS = ["patient_id", "outcome_code", "outcome_at", "label"]
ENCOUNTER_COLUMNS = ["patient_id", "encountered_at", "encounter_type"]
DATA_DICTIONARY_COLUMNS = [
    "variable_code",
    "display_name",
    "unit",
    "domain",
    "is_treatment_related",
    "is_outcome_derived",
    "is_post_index_only",
]


def _frame_from_models(items: list[BaseModel], columns: list[str]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame([item.model_dump(mode="json") for item in items], columns=columns)


def dataset_to_frames(dataset: DatasetPayload) -> dict[str, pd.DataFrame]:
    """Convert a typed dataset payload into pandas DataFrames."""

    return {
        "participants": _frame_from_models(dataset.participants, PARTICIPANT_COLUMNS),
        "observations": _frame_from_models(dataset.observations, OBSERVATION_COLUMNS),
        "outcomes": _frame_from_models(dataset.outcomes, OUTCOME_COLUMNS),
        "encounters": _frame_from_models(dataset.encounters, ENCOUNTER_COLUMNS),
        "data_dictionary": _frame_from_models(dataset.data_dictionary, DATA_DICTIONARY_COLUMNS),
    }
