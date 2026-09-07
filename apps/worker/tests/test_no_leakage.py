import pandas as pd

from app.pipeline.models import _static_feature_frame
from app.pipeline.trajectories import build_trajectory_features


def test_trajectory_features_exclude_observations_at_or_after_cutoff() -> None:
    cohort = pd.DataFrame(
        [
            {
                "patient_id": "SYN-0001",
                "index_date": pd.Timestamp("2026-01-10T00:00:00Z"),
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


def test_static_encounter_features_exclude_post_cutoff_records() -> None:
    cohort = pd.DataFrame(
        [
            {
                "patient_id": "SYN-0001",
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

    static_features = _static_feature_frame(cohort, participants, encounters)
    assert int(static_features.loc["SYN-0001", "encounter_count"]) == 1
