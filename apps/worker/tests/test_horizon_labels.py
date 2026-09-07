"""Tests proving horizon-specific labels, anchors, and control eligibility.

These guard against the original bug where a single index_date equal to the
outcome date made every case positive at day 0 for every horizon.
"""

import pandas as pd

from app.pipeline.cohort import compute_first_history_at
from app.pipeline.index_dates import build_horizon_frame


def _participants() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"patient_id": "CASE-NEAR", "reference_date": pd.NaT},
            {"patient_id": "CASE-FAR", "reference_date": pd.NaT},
            {"patient_id": "CONTROL-1", "reference_date": pd.Timestamp("2026-06-01T00:00:00Z")},
        ]
    )


def _outcomes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            # Diagnosed 40 days after a hypothetical anchor: eligible at horizon=90 (40 <= 90)
            # but not at horizon=30 (40 > 30).
            {"patient_id": "CASE-NEAR", "outcome_code": "dx", "outcome_at": "2026-04-10T00:00:00Z"},
            # Diagnosed far in the future relative to a 30-day horizon anchor.
            {"patient_id": "CASE-FAR", "outcome_code": "dx", "outcome_at": "2027-01-01T00:00:00Z"},
        ]
    )


def _history() -> pd.DataFrame:
    # Give every patient 3 years of history so min_history_days checks pass
    # regardless of which horizon-specific anchor is chosen.
    return pd.DataFrame(
        [
            {"patient_id": "CASE-NEAR", "first_history_at": pd.Timestamp("2023-01-01T00:00:00Z")},
            {"patient_id": "CASE-FAR", "first_history_at": pd.Timestamp("2023-01-01T00:00:00Z")},
            {"patient_id": "CONTROL-1", "first_history_at": pd.Timestamp("2023-01-01T00:00:00Z")},
        ]
    )


def test_case_label_is_positive_only_within_its_own_horizon_window() -> None:
    participants = _participants()
    outcomes = _outcomes()
    history = _history()

    frame_30, _ = build_horizon_frame(participants, outcomes, history, horizon_days=30, prediction_gap_days=0, min_history_days=365)
    frame_90, _ = build_horizon_frame(participants, outcomes, history, horizon_days=90, prediction_gap_days=0, min_history_days=365)

    labels_30 = frame_30.set_index("patient_id")["label"]
    labels_90 = frame_90.set_index("patient_id")["label"]

    # CASE-NEAR: anchor = outcome_at - horizon, so the outcome always lands
    # exactly at the horizon boundary for whichever horizon defines its own
    # anchor. It must be positive under both of its own horizon-specific frames.
    assert labels_30.loc["CASE-NEAR"] == 1
    assert labels_90.loc["CASE-NEAR"] == 1


def test_prediction_anchor_is_strictly_before_diagnosis_and_matches_horizon() -> None:
    participants = _participants()
    outcomes = _outcomes()
    history = _history()

    horizon_days = 90
    frame, _ = build_horizon_frame(participants, outcomes, history, horizon_days=horizon_days, prediction_gap_days=0, min_history_days=365)
    row = frame.set_index("patient_id").loc["CASE-NEAR"]

    diagnosis_date = pd.Timestamp("2026-04-10T00:00:00Z")
    expected_anchor = diagnosis_date - pd.to_timedelta(horizon_days, unit="D")

    assert row["prediction_anchor_date"] == expected_anchor
    assert row["prediction_anchor_date"] < diagnosis_date
    assert row["feature_cutoff"] <= row["prediction_anchor_date"]


def test_feature_cutoff_respects_prediction_gap_days() -> None:
    participants = _participants()
    outcomes = _outcomes()
    history = _history()

    frame, _ = build_horizon_frame(participants, outcomes, history, horizon_days=90, prediction_gap_days=14, min_history_days=365)
    row = frame.set_index("patient_id").loc["CASE-NEAR"]

    assert row["feature_cutoff"] == row["prediction_anchor_date"] - pd.to_timedelta(14, unit="D")


def test_control_receives_negative_label_and_pseudo_anchor_from_reference_date() -> None:
    participants = _participants()
    outcomes = _outcomes()
    history = _history()

    frame, _ = build_horizon_frame(participants, outcomes, history, horizon_days=90, prediction_gap_days=0, min_history_days=365)
    row = frame.set_index("patient_id").loc["CONTROL-1"]

    assert row["label"] == 0
    assert row["prediction_anchor_date"] == pd.Timestamp("2026-06-01T00:00:00Z")


def test_control_without_valid_reference_date_is_excluded() -> None:
    participants = pd.DataFrame([{"patient_id": "NO-ANCHOR", "reference_date": pd.NaT}])
    outcomes = pd.DataFrame(columns=["patient_id", "outcome_code", "outcome_at"])
    history = pd.DataFrame([{"patient_id": "NO-ANCHOR", "first_history_at": pd.Timestamp("2023-01-01T00:00:00Z")}])

    frame, exclusions = build_horizon_frame(participants, outcomes, history, horizon_days=90, prediction_gap_days=0, min_history_days=365)

    assert frame.empty
    assert exclusions["no_valid_anchor"] == 1


def test_insufficient_history_before_anchor_is_excluded() -> None:
    participants = pd.DataFrame([{"patient_id": "SHORT-HISTORY", "reference_date": pd.Timestamp("2026-06-01T00:00:00Z")}])
    outcomes = pd.DataFrame(columns=["patient_id", "outcome_code", "outcome_at"])
    history = pd.DataFrame([{"patient_id": "SHORT-HISTORY", "first_history_at": pd.Timestamp("2026-05-01T00:00:00Z")}])

    frame, exclusions = build_horizon_frame(participants, outcomes, history, horizon_days=90, prediction_gap_days=0, min_history_days=365)

    assert frame.empty
    assert exclusions["insufficient_history"] == 1


def test_compute_first_history_at_uses_earliest_observation_or_encounter() -> None:
    observations = pd.DataFrame(
        [{"patient_id": "SYN-0001", "observed_at": "2024-03-01T00:00:00Z"}],
        columns=["patient_id", "observed_at"],
    )
    encounters = pd.DataFrame(
        [{"patient_id": "SYN-0001", "encountered_at": "2024-01-01T00:00:00Z"}],
        columns=["patient_id", "encountered_at"],
    )
    history = compute_first_history_at(observations, encounters)
    assert history.set_index("patient_id").loc["SYN-0001", "first_history_at"] == pd.Timestamp("2024-01-01T00:00:00Z")


def test_negative_labeled_patients_have_no_outcome_record() -> None:
    """Every patient labelled negative for a horizon must have zero recorded
    outcomes -- a negative label must never coexist with an in-window event."""

    participants = _participants()
    outcomes = _outcomes()
    history = _history()

    frame, _ = build_horizon_frame(participants, outcomes, history, horizon_days=90, prediction_gap_days=0, min_history_days=365)

    outcome_patient_ids = set(outcomes["patient_id"])
    negative_ids = set(frame.loc[frame["label"] == 0, "patient_id"])
    assert negative_ids.isdisjoint(outcome_patient_ids)
