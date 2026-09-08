import pandas as pd

from app.pipeline.trajectories import build_trajectory_features


def test_trajectory_window_slope_uses_only_the_pre_cutoff_window() -> None:
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
            {
                "patient_id": "SYN-0001",
                "variable_code": "lab_a",
                "value": 0.0,
                "observed_at": "2025-01-01T00:00:00Z",
                "unit": "u/L",
            },
            {
                "patient_id": "SYN-0001",
                "variable_code": "lab_a",
                "value": 1.0,
                "observed_at": "2025-12-20T00:00:00Z",
                "unit": "u/L",
            },
            {
                "patient_id": "SYN-0001",
                "variable_code": "lab_a",
                "value": 3.0,
                "observed_at": "2026-01-05T00:00:00Z",
                "unit": "u/L",
            },
            {
                "patient_id": "SYN-0001",
                "variable_code": "lab_a",
                "value": 999.0,
                "observed_at": "2026-01-08T00:00:00Z",
                "unit": "u/L",
            },
        ]
    )
    dictionary = pd.DataFrame([{"variable_code": "lab_a", "unit": "u/L"}])

    result = build_trajectory_features(
        cohort, observations, dictionary, min_observations_per_variable=2
    )
    feature = "traj__lab_a__ols_slope_30d"
    manifest = next(
        item for item in result.feature_manifest if item["feature"] == feature
    )

    assert result.features.loc[0, feature] is not None
    assert manifest["window_days"] == 30
    assert manifest["pre_index_only"] is True
    assert manifest["source_timestamps_used"] == [
        "2025-12-20T00:00:00+00:00",
        "2026-01-05T00:00:00+00:00",
    ]
