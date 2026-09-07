"""Cohort construction and simple inclusion/exclusion logic."""

from __future__ import annotations

import pandas as pd


def build_cohort(
    participants: pd.DataFrame,
    observations: pd.DataFrame,
    encounters: pd.DataFrame,
    index_dates: pd.DataFrame,
    min_history_days: int,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Build an eligible cohort and summarize exclusions."""

    participants = participants.copy()
    cohort = participants.merge(index_dates, on="patient_id", how="left")
    exclusions = {"missing_index_date": 0, "missing_history": 0, "insufficient_history": 0}

    event_frames: list[pd.DataFrame] = []
    if not observations.empty:
        obs = observations[["patient_id", "observed_at"]].copy()
        obs["event_at"] = pd.to_datetime(obs["observed_at"], utc=True, errors="coerce")
        event_frames.append(obs[["patient_id", "event_at"]])
    if not encounters.empty:
        enc = encounters[["patient_id", "encountered_at"]].copy()
        enc["event_at"] = pd.to_datetime(enc["encountered_at"], utc=True, errors="coerce")
        event_frames.append(enc[["patient_id", "event_at"]])

    history = pd.DataFrame(columns=["patient_id", "first_history_at"])
    if event_frames:
        all_events = pd.concat(event_frames, ignore_index=True)
        history = (
            all_events.dropna(subset=["event_at"])
            .groupby("patient_id", as_index=False)["event_at"]
            .min()
            .rename(columns={"event_at": "first_history_at"})
        )

    cohort = cohort.merge(history, on="patient_id", how="left")
    cohort["index_date"] = pd.to_datetime(cohort["index_date"], utc=True, errors="coerce")
    cohort["first_history_at"] = pd.to_datetime(cohort["first_history_at"], utc=True, errors="coerce")

    exclusions["missing_index_date"] = int(cohort["index_date"].isna().sum())
    exclusions["missing_history"] = int(cohort["first_history_at"].isna().sum())

    cohort = cohort.dropna(subset=["index_date", "first_history_at"]).copy()
    cohort["history_days"] = (cohort["index_date"] - cohort["first_history_at"]).dt.days
    insufficient_mask = cohort["history_days"] < min_history_days
    exclusions["insufficient_history"] = int(insufficient_mask.sum())
    cohort = cohort.loc[~insufficient_mask].copy()
    return cohort.reset_index(drop=True), exclusions
