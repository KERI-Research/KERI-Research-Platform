import pandas as pd

from app.pipeline import models


def test_m5_uses_only_trajectory_features(monkeypatch) -> None:
    patient_ids = [f"SYN-{index:04d}" for index in range(40)]
    labels = pd.Series([1] * 10 + [0] * 30, index=patient_ids)
    static_features = pd.DataFrame(
        {
            "age": [50.0] * 40,
            "sex": ["F"] * 40,
            "history_days": [400] * 40,
            "encounter_count": [2] * 40,
            "encounters_per_year": [1.5] * 40,
        },
        index=patient_ids,
    )
    trajectory_features = pd.DataFrame(
        {
            "patient_id": patient_ids,
            "traj__haemoglobin__ols_slope": [0.1] * 40,
        }
    )
    captured_columns: dict[str, list[str]] = {}

    def capture_fit(model_name, _model, X_train, *_args):
        captured_columns[model_name] = list(X_train.columns)
        return {"status": "evaluated", "metrics": {"auroc": 0.7}}

    monkeypatch.setattr(models, "_fit_single_model", capture_fit)
    monkeypatch.setattr(
        models,
        "patient_level_split",
        lambda *_args, **_kwargs: (
            patient_ids[:5] + patient_ids[10:30],
            patient_ids[5:10] + patient_ids[30:],
        ),
    )

    result = models.fit_horizon_model_suite(
        static_features,
        trajectory_features,
        labels,
        patient_ids,
        horizon_days=365,
    )

    assert captured_columns["M5"] == ["traj__haemoglobin__ols_slope"]
    assert result["model_results"]["M5"]["status"] == "evaluated"
