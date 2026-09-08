import pandas as pd
from xgboost import XGBClassifier

from app.pipeline import models


def test_m3_and_m4_use_class_weighted_xgboost(monkeypatch) -> None:
    patient_ids = [f"SYN-{index:04d}" for index in range(40)]
    labels = pd.Series([1] * 10 + [0] * 30, index=patient_ids)
    static_features = pd.DataFrame(
        {
            "age": [50.0] * 40,
            "sex": ["F"] * 40,
            "encounter_count": [2] * 40,
            "encounters_per_year": [1.5] * 40,
            "history_days": [400] * 40,
        },
        index=patient_ids,
    )
    trajectory_features = pd.DataFrame(
        {"patient_id": patient_ids, "traj__lab__slope": [0.1] * 40}
    )
    captured_models = {}

    def capture_model(model_name, model, *_):
        captured_models[model_name] = model
        return {"status": "evaluated", "metrics": {"auroc": 0.7}}

    monkeypatch.setattr(models, "_fit_single_model", capture_model)
    monkeypatch.setattr(
        models,
        "patient_level_split",
        lambda *_args, **_kwargs: (
            patient_ids[:5] + patient_ids[10:30],
            patient_ids[5:10] + patient_ids[30:],
        ),
    )
    models.fit_horizon_model_suite(
        static_features, trajectory_features, labels, patient_ids, horizon_days=365
    )

    for model_name in ("M3", "M4"):
        assert isinstance(captured_models[model_name], XGBClassifier)
        assert captured_models[model_name].get_params()["scale_pos_weight"] == 4.0
