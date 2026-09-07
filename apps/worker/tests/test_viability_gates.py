import pandas as pd

from app.pipeline.models import fit_horizon_model_suite


def test_insufficient_outcomes_or_history_returns_not_evaluable() -> None:
    patient_ids = [f"SYN-{index:04d}" for index in range(1, 11)]
    static_features = pd.DataFrame(
        {
            "age": [50 + index for index in range(10)],
            "sex": ["F", "M"] * 5,
            "history_days": [400] * 10,
            "encounter_count": [2] * 10,
            "encounters_per_year": [1.5] * 10,
            "cohort_label": ["synthetic"] * 10,
        },
        index=patient_ids,
    )
    trajectory_features = pd.DataFrame({"patient_id": patient_ids})
    labels = pd.Series([1, 0, 0, 0, 0, 0, 0, 0, 0, 0], index=patient_ids)

    result = fit_horizon_model_suite(
        static_features=static_features,
        trajectory_features=trajectory_features,
        labels=labels,
        patient_ids=patient_ids,
        horizon_days=365,
    )

    assert result["viability"]["is_viable"] is False
    assert {item["status"] for item in result["model_results"].values()} == {"not_evaluable"}
