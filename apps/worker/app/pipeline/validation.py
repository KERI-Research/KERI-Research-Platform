"""Schema and leakage-oriented validation for synthetic research payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass
class SchemaValidationError(Exception):
    """Raised when a dataset payload fails schema validation."""

    problems: list[str]

    def __str__(self) -> str:
        return "; ".join(self.problems)


REQUIRED_COLUMNS: dict[str, set[str]] = {
    "participants": {"patient_id"},
    "observations": {"patient_id", "variable_code", "value", "observed_at"},
    "outcomes": {"patient_id", "outcome_code", "outcome_at"},
    "encounters": {"patient_id", "encountered_at"},
    "data_dictionary": {"variable_code"},
}
TIMESTAMP_COLUMNS: dict[str, tuple[str, ...]] = {
    "participants": ("diagnosis_date", "reference_date"),
    "observations": ("observed_at",),
    "outcomes": ("outcome_at",),
    "encounters": ("encountered_at",),
}


def _existing_columns(frame: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    return [column for column in columns if column in frame.columns]


def validate_frames(frames: dict[str, pd.DataFrame]) -> None:
    """Validate table schemas and reject obviously leaky feature sources."""

    problems: list[str] = []

    for table_name, required_columns in REQUIRED_COLUMNS.items():
        frame = frames.get(table_name, pd.DataFrame())
        missing = sorted(required_columns - set(frame.columns))
        if missing:
            problems.append(f"{table_name} missing required columns: {', '.join(missing)}")

    for table_name, timestamp_columns in TIMESTAMP_COLUMNS.items():
        frame = frames.get(table_name, pd.DataFrame())
        for column in _existing_columns(frame, timestamp_columns):
            converted = pd.to_datetime(frame[column], errors="coerce", utc=True)
            invalid_mask = frame[column].notna() & converted.isna()
            if invalid_mask.any():
                row_ids = list(frame.index[invalid_mask][:5])
                problems.append(f"{table_name}.{column} contains invalid timestamps at rows {row_ids}")

    data_dictionary = frames.get("data_dictionary", pd.DataFrame())
    observations = frames.get("observations", pd.DataFrame())
    if not data_dictionary.empty and not observations.empty and "variable_code" in observations.columns:
        forbidden_flags = [
            flag
            for flag in ("is_treatment_related", "is_outcome_derived", "is_post_index_only")
            if flag in data_dictionary.columns
        ]
        if forbidden_flags:
            forbidden_mask = data_dictionary[forbidden_flags].fillna(False).astype(bool).any(axis=1)
            forbidden_codes = set(data_dictionary.loc[forbidden_mask, "variable_code"].astype(str))
            leaking_codes = sorted(set(observations["variable_code"].astype(str)) & forbidden_codes)
            if leaking_codes:
                problems.append(
                    "observations include forbidden variable codes flagged as treatment-related, "
                    f"outcome-derived, or post-index only: {', '.join(leaking_codes)}"
                )

    if problems:
        raise SchemaValidationError(problems)
