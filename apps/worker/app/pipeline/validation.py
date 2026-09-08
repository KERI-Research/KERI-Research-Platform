"""Schema and leakage-oriented validation for synthetic research payloads."""

from __future__ import annotations

from dataclasses import dataclass
import re
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
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _looks_like_nhs_number(value: str) -> bool:
    digits = re.sub(r"[\s-]", "", value)
    if not re.fullmatch(r"\d{10}", digits):
        return False
    weighted_sum = sum(
        int(digit) * weight
        for digit, weight in zip(digits[:9], range(10, 1, -1), strict=True)
    )
    check_digit = 11 - (weighted_sum % 11)
    if check_digit == 11:
        check_digit = 0
    return check_digit != 10 and check_digit == int(digits[9])


def _existing_columns(frame: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    return [column for column in columns if column in frame.columns]


def validate_frames(frames: dict[str, pd.DataFrame]) -> None:
    """Validate table schemas and reject obviously leaky feature sources."""

    problems: list[str] = []

    for table_name, required_columns in REQUIRED_COLUMNS.items():
        frame = frames.get(table_name, pd.DataFrame())
        missing = sorted(required_columns - set(frame.columns))
        if missing:
            problems.append(
                f"{table_name} missing required columns: {', '.join(missing)}"
            )

    for table_name, timestamp_columns in TIMESTAMP_COLUMNS.items():
        frame = frames.get(table_name, pd.DataFrame())
        for column in _existing_columns(frame, timestamp_columns):
            converted = pd.to_datetime(frame[column], errors="coerce", utc=True)
            invalid_mask = frame[column].notna() & converted.isna()
            if invalid_mask.any():
                row_ids = list(frame.index[invalid_mask][:5])
                problems.append(
                    f"{table_name}.{column} contains invalid timestamps at rows {row_ids}"
                )

    participants = frames.get("participants", pd.DataFrame())
    if "patient_id" in participants.columns:
        participant_ids = participants["patient_id"].dropna().astype(str)
        if participant_ids.duplicated().any():
            problems.append("participants contains duplicate patient_id values")
        if participant_ids.map(
            lambda value: bool(EMAIL_PATTERN.fullmatch(value))
            or _looks_like_nhs_number(value)
        ).any():
            problems.append(
                "participants.patient_id appears to contain a direct identifier rather than a pseudonym"
            )
        known_patient_ids = set(participant_ids)
        for table_name in ("observations", "outcomes", "encounters"):
            frame = frames.get(table_name, pd.DataFrame())
            if "patient_id" not in frame.columns:
                continue
            unknown_count = int(
                (~frame["patient_id"].astype(str).isin(known_patient_ids)).sum()
            )
            if unknown_count:
                problems.append(
                    f"{table_name} contains {unknown_count} records for unknown participants"
                )

    data_dictionary = frames.get("data_dictionary", pd.DataFrame())
    observations = frames.get("observations", pd.DataFrame())
    if (
        not data_dictionary.empty
        and not observations.empty
        and "variable_code" in observations.columns
    ):
        if data_dictionary["variable_code"].dropna().astype(str).duplicated().any():
            problems.append("data_dictionary contains duplicate variable_code values")

        dictionary_codes = set(data_dictionary["variable_code"].dropna().astype(str))
        observation_codes = set(observations["variable_code"].dropna().astype(str))
        undocumented_codes = sorted(observation_codes - dictionary_codes)
        if undocumented_codes:
            problems.append(
                "observations include variable codes missing from data_dictionary: "
                f"{', '.join(undocumented_codes)}"
            )

        if "unit" in observations.columns and "unit" in data_dictionary.columns:
            expected_units = (
                data_dictionary.dropna(subset=["variable_code", "unit"])
                .assign(
                    variable_code=lambda frame: frame["variable_code"].astype(str),
                    unit=lambda frame: frame["unit"]
                    .astype(str)
                    .str.strip()
                    .str.lower(),
                )
                .drop_duplicates("variable_code")
                .set_index("variable_code")["unit"]
            )
            observed_units = observations.assign(
                variable_code=lambda frame: frame["variable_code"].astype(str),
                unit=lambda frame: frame["unit"].astype(str).str.strip().str.lower(),
            )
            expected_for_observation = observed_units["variable_code"].map(
                expected_units
            )
            mismatched_codes = sorted(
                set(
                    observed_units.loc[
                        expected_for_observation.notna()
                        & observed_units["unit"].ne(expected_for_observation),
                        "variable_code",
                    ]
                )
            )
            if mismatched_codes:
                problems.append(
                    "observations contain units that do not match data_dictionary canonical units for: "
                    f"{', '.join(mismatched_codes)}"
                )

        forbidden_flags = [
            flag
            for flag in (
                "is_treatment_related",
                "is_outcome_derived",
                "is_post_index_only",
            )
            if flag in data_dictionary.columns
        ]
        if forbidden_flags:
            forbidden_mask = (
                data_dictionary[forbidden_flags].fillna(False).astype(bool).any(axis=1)
            )
            forbidden_codes = set(
                data_dictionary.loc[forbidden_mask, "variable_code"].astype(str)
            )
            leaking_codes = sorted(
                set(observations["variable_code"].astype(str)) & forbidden_codes
            )
            if leaking_codes:
                problems.append(
                    "observations include forbidden variable codes flagged as treatment-related, "
                    f"outcome-derived, or post-index only: {', '.join(leaking_codes)}"
                )

    if problems:
        raise SchemaValidationError(problems)
