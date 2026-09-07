"""Shared cohort history helpers used when building horizon-specific frames."""

from __future__ import annotations

import pandas as pd


def compute_first_history_at(observations: pd.DataFrame, encounters: pd.DataFrame) -> pd.DataFrame:
    """Return each patient's earliest recorded observation/encounter timestamp.

    This marks the start of a patient's available history and is used to check
    that enough pre-anchor history exists for a given horizon's prediction
    anchor date. It does not depend on outcome/case status.
    """

    event_frames: list[pd.DataFrame] = []
    if not observations.empty:
        obs = observations[["patient_id", "observed_at"]].copy()
        obs["event_at"] = pd.to_datetime(obs["observed_at"], utc=True, errors="coerce")
        event_frames.append(obs[["patient_id", "event_at"]])
    if not encounters.empty:
        enc = encounters[["patient_id", "encountered_at"]].copy()
        enc["event_at"] = pd.to_datetime(enc["encountered_at"], utc=True, errors="coerce")
        event_frames.append(enc[["patient_id", "event_at"]])

    if not event_frames:
        return pd.DataFrame(columns=["patient_id", "first_history_at"])

    all_events = pd.concat(event_frames, ignore_index=True)
    return (
        all_events.dropna(subset=["event_at"])
        .groupby("patient_id", as_index=False)["event_at"]
        .min()
        .rename(columns={"event_at": "first_history_at"})
    )
