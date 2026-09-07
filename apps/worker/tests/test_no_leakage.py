import pandas as pd

from app.pipeline.models import _static_feature_frame
from app.pipeline.trajectories import build_trajectory_features


def test_trajectory_features_exclude_observations_at_or_after_cutoff() -> None:
    cohort = pd.DataFrame(
        [
            {
                "patient_id": "SYN-0001",
                "prediction_anchor_date": pd.Timestamp("2026-01-10T00:00:00Z"),
                "feature_cutoff": pd.Timestamp("2026-01-08T00:00:00Z"),
            }
        ]
    )
    observations = pd.DataFrame(
        [
            {"patient_id": "SYN-0001", "variable_code": "lab_a", "value": 1.0, "observed_at": "2026-01-01T00:00:00Z", "unit": "u/L"},
            {"patient_id": "SYN-0001", "variable_code": "lab_a", "value": 2.0, "observed_at": "2026-01-07T00:00:00Z", "unit": "u/L"},
            {"patient_id": "SYN-0001", "variable_code": "lab_a", "value": 99.0, "observed_at": "2026-01-08T00:00:00Z", "unit": "u/L"},
            {"patient_id": "SYN-0001", "variable_code": "lab_a", "value": 100.0, "observed_at": "2026-01-09T00:00:00Z", "unit": "u/L"},
        ]
    )
    data_dictionary = pd.DataFrame([{"variable_code": "lab_a", "unit": "u/L"}])

    result = build_trajectory_features(cohort, observations, data_dictionary, min_observations_per_variable=2)
    feature_row = result.features.set_index("patient_id").loc["SYN-0001"]
    assert feature_row["traj__lab_a__observation_count"] == 2

    manifest = result.feature_manifest[0]
    assert manifest["source_timestamps_used"] == [
        "2026-01-01T00:00:00+00:00",
        "2026-01-07T00:00:00+00:00",
    ]
    # The observation exactly at, and the one after, feature_cutoff must never
    # appear in the timestamps used to derive features.
    assert "2026-01-08T00:00:00+00:00" not in manifest["source_timestamps_used"]
    assert "2026-01-09T00:00:00+00:00" not in manifest["source_timestamps_used"]


def test_static_encounter_features_exclude_post_cutoff_records() -> None:
    cohort = pd.DataFrame(
        [
            {
                "patient_id": "SYN-0001",
                "prediction_anchor_date": pd.Timestamp("2026-01-10T00:00:00Z"),
                "feature_cutoff": pd.Timestamp("2026-01-08T00:00:00Z"),
                "history_days": 400,
            }
        ]
    )
    participants = pd.DataFrame(
        [{"patient_id": "SYN-0001", "age": 60.0, "sex": "F", "cohort_label": "synthetic"}]
    )
    encounters = pd.DataFrame(
        [
            {"patient_id": "SYN-0001", "encountered_at": "2026-01-01T00:00:00Z"},
            {"patient_id": "SYN-0001", "encountered_at": "2026-01-09T00:00:00Z"},
        ]
    )
    observations = pd.DataFrame(columns=["patient_id", "variable_code", "value", "observed_at", "unit"])

    static_features = _static_feature_frame(cohort, participants, encounters, observations)
    assert int(static_features.loc["SYN-0001", "encounter_count"]) == 1


def test_static_measurement_features_use_last_pre_cutoff_value() -> None:
    cohort = pd.DataFrame(
        [
            {
                "patient_id": "SYN-0001",
                "prediction_anchor_date": pd.Timestamp("2026-01-10T00:00:00Z"),
                "feature_cutoff": pd.Timestamp("2026-01-08T00:00:00Z"),
                "history_days": 400,
            }
        ]
    )
    participants = pd.DataFrame([{"patient_id": "SYN-0001", "age": 60.0, "sex": "F"}])
    encounters = pd.DataFrame(columns=["patient_id", "encountered_at"])
    observations = pd.DataFrame(
        [
            {"patient_id": "SYN-0001", "variable_code": "lab_a", "value": 5.0, "observed_at": "2026-01-01T00:00:00Z", "unit": "u/L"},
            {"patient_id": "SYN-0001", "variable_code": "lab_a", "value": 7.0, "observed_at": "2026-01-07T00:00:00Z", "unit": "u/L"},
            {"patient_id": "SYN-0001", "variable_code": "lab_a", "value": 999.0, "observed_at": "2026-01-08T00:00:00Z", "unit": "u/L"},
            {"patient_id": "SYN-0001", "variable_code": "lab_a", "value": 999.0, "observed_at": "2026-01-09T00:00:00Z", "unit": "u/L"},
        ]
    )

    static_features = _static_feature_frame(cohort, participants, encounters, observations)
    assert static_features.loc["SYN-0001", "static__lab_a__last_value"] == 7.0
    assert static_features.loc["SYN-0001", "static__lab_a__days_since_last_measurement"] == 3.0


def test_static_features_never_include_forbidden_outcome_derived_columns() -> None:
    """Static feature matrices must never contain post-index, outcome-derived,
    treatment-related, or cohort-assignment fields."""

    cohort = pd.DataFrame(
        [
            {
                "patient_id": "SYN-0001",
                "prediction_anchor_date": pd.Timestamp("2026-01-10T00:00:00Z"),
                "feature_cutoff": pd.Timestamp("2026-01-08T00:00:00Z"),
                "history_days": 400,
            }
        ]
    )
    participants = pd.DataFrame(
        [
            {
                "patient_id": "SYN-0001",
                "age": 60.0,
                "sex": "F",
                "cohort_label": "case",
                "diagnosis_date": "2026-01-10T00:00:00Z",
                "reference_date": "2025-01-01T00:00:00Z",
            }
        ]
    )
    encounters = pd.DataFrame(columns=["patient_id", "encountered_at"])
    observations = pd.DataFrame(columns=["patient_id", "variable_code", "value", "observed_at", "unit"])

    static_features = _static_feature_frame(cohort, participants, encounters, observations)
    forbidden_columns = {"cohort_label", "diagnosis_date", "reference_date", "label", "incident_flag", "outcome_at"}
    assert forbidden_columns.isdisjoint(static_features.columns)
