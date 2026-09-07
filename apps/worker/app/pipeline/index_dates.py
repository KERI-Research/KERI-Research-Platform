"""Index-date computation utilities for synthetic case/control research scaffolds."""

from __future__ import annotations

import pandas as pd


def compute_index_dates(
    participants: pd.DataFrame,
    outcomes: pd.DataFrame,
    prediction_gap_days: int,
) -> pd.DataFrame:
    """Compute index dates and strict feature cutoffs.

    Cases use the earliest recorded outcome date. Controls fall back to a participant
    reference date and then diagnosis_date when present.
    """

    participants = participants.copy()
    if participants.empty:
        return pd.DataFrame(columns=["patient_id", "index_date", "feature_cutoff"])

    for column in ("diagnosis_date", "reference_date"):
        if column in participants.columns:
            participants[column] = pd.to_datetime(participants[column], utc=True, errors="coerce")

    outcome_index = pd.DataFrame(columns=["patient_id", "case_index_date"])
    if not outcomes.empty:
        outcome_frame = outcomes.copy()
        outcome_frame["outcome_at"] = pd.to_datetime(outcome_frame["outcome_at"], utc=True, errors="coerce")
        outcome_index = (
            outcome_frame.dropna(subset=["outcome_at"])
            .groupby("patient_id", as_index=False)["outcome_at"]
            .min()
            .rename(columns={"outcome_at": "case_index_date"})
        )

    merged = participants.merge(outcome_index, on="patient_id", how="left")
    merged["index_date"] = merged["case_index_date"]
    if "reference_date" in merged.columns:
        merged["index_date"] = merged["index_date"].fillna(merged["reference_date"])
    if "diagnosis_date" in merged.columns:
        merged["index_date"] = merged["index_date"].fillna(merged["diagnosis_date"])

    merged["feature_cutoff"] = merged["index_date"] - pd.to_timedelta(prediction_gap_days, unit="D")
    return merged[["patient_id", "index_date", "feature_cutoff"]]
