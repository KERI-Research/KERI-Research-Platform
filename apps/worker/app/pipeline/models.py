"""Model preparation, viability gating, and training for synthetic comparisons."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.pipeline.evaluate import compute_metrics, model_comparison_deltas
from app.pipeline.splits import patient_level_split

MIN_SUFFICIENT_HISTORY_PATIENTS = 20
MIN_HISTORY_MULTIPLIER = 2


def check_viability(
    n_outcomes: int,
    n_with_sufficient_history: int,
    horizon_days: int,
    min_required: int = 8,
) -> tuple[bool, str]:
    """Return whether a horizon is worth evaluating in this synthetic scaffold."""

    if horizon_days <= 0:
        return False, "Horizon must be positive."
    if n_with_sufficient_history < max(MIN_SUFFICIENT_HISTORY_PATIENTS, min_required * MIN_HISTORY_MULTIPLIER):
        return False, "Too few patients with sufficient history for a stable comparison."
    if n_outcomes < min_required:
        return False, "Too few positive outcomes for a stable feasibility estimate."
    return True, "Viable for synthetic feasibility modelling."


def _make_one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def build_preprocessor(feature_frame: pd.DataFrame) -> ColumnTransformer:
    """Build a preprocessing transformer fit only within a training pipeline."""

    numeric_columns = [column for column in feature_frame.columns if pd.api.types.is_numeric_dtype(feature_frame[column])]
    categorical_columns = [column for column in feature_frame.columns if column not in numeric_columns]

    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", _make_one_hot_encoder()),
        ]
    )

    transformers = []
    if numeric_columns:
        transformers.append(("numeric", numeric_pipeline, numeric_columns))
    if categorical_columns:
        transformers.append(("categorical", categorical_pipeline, categorical_columns))

    return ColumnTransformer(transformers=transformers, remainder="drop")


def build_model_pipeline(model: Any, feature_frame: pd.DataFrame) -> Pipeline:
    """Return a pipeline that guarantees train-only preprocessing fit."""

    return Pipeline(
        steps=[
            ("preprocessor", build_preprocessor(feature_frame)),
            ("model", model),
        ]
    )


def _static_feature_frame(
    cohort: pd.DataFrame,
    participants: pd.DataFrame,
    encounters: pd.DataFrame,
) -> pd.DataFrame:
    participant_frame = participants.copy()
    encounter_frame = encounters.copy()
    static = cohort[["patient_id", "history_days"]].copy()
    static = static.merge(participant_frame, on="patient_id", how="left")

    if not encounter_frame.empty:
        encounter_frame["encountered_at"] = pd.to_datetime(encounter_frame["encountered_at"], utc=True, errors="coerce")
        cutoff_frame = cohort[["patient_id", "feature_cutoff"]].copy()
        cutoff_frame["feature_cutoff"] = pd.to_datetime(cutoff_frame["feature_cutoff"], utc=True, errors="coerce")
        encounter_frame = encounter_frame.merge(cutoff_frame, on="patient_id", how="inner")
        encounter_frame = encounter_frame.loc[encounter_frame["encountered_at"] < encounter_frame["feature_cutoff"]]
        encounter_counts = encounter_frame.groupby("patient_id").size().rename("encounter_count").reset_index()
        static = static.merge(encounter_counts, on="patient_id", how="left")
    else:
        static["encounter_count"] = 0

    static["encounter_count"] = static["encounter_count"].fillna(0)
    static["age"] = static.get("age", pd.Series(dtype=float)).astype(float)
    static["sex"] = static.get("sex", pd.Series(dtype=object)).fillna("unknown")
    static["cohort_label"] = static.get("cohort_label", pd.Series(dtype=object)).fillna("synthetic")
    static["encounters_per_year"] = static["encounter_count"] / np.maximum(static["history_days"] / 365.0, 1e-6)
    return static.set_index("patient_id")


def _labels_by_horizon(
    cohort: pd.DataFrame,
    outcomes: pd.DataFrame,
    horizons: list[int],
) -> dict[int, pd.Series]:
    labels: dict[int, pd.Series] = {}
    outcomes_frame = outcomes.copy()
    outcomes_frame["outcome_at"] = pd.to_datetime(outcomes_frame["outcome_at"], utc=True, errors="coerce")

    for horizon in horizons:
        frame = cohort[["patient_id", "index_date"]].copy()
        frame["index_date"] = pd.to_datetime(frame["index_date"], utc=True, errors="coerce")
        merged = frame.merge(outcomes_frame[["patient_id", "outcome_at"]], on="patient_id", how="left")
        merged["days_to_outcome"] = (merged["outcome_at"] - merged["index_date"]).dt.days
        positive = merged.groupby("patient_id")["days_to_outcome"].apply(
            lambda s: int(((s >= 0) & (s <= horizon)).any())
        )
        labels[horizon] = positive.reindex(frame["patient_id"]).fillna(0).astype(int)
    return labels


def _fit_single_model(
    model_name: str,
    model: Any,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, Any]:
    pipeline = build_model_pipeline(model, X_train)
    pipeline.fit(X_train, y_train)
    y_prob = pipeline.predict_proba(X_test)[:, 1]
    return {
        "status": "evaluated",
        "metrics": compute_metrics(y_test.to_numpy(), y_prob),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "model_name": model_name,
    }


def fit_horizon_model_suite(
    static_features: pd.DataFrame,
    trajectory_features: pd.DataFrame,
    labels: pd.Series,
    patient_ids: list[str],
    horizon_days: int,
    random_state: int = 42,
    test_size: float = 0.25,
) -> dict[str, Any]:
    """Fit the five comparison models for one horizon, or return NOT_EVALUABLE results."""

    viable, reason = check_viability(int(labels.sum()), len(patient_ids), horizon_days)
    model_names = ["M0", "M1", "M2", "M3", "M4"]
    if not viable:
        return {
            "horizon_days": horizon_days,
            "viability": {"is_viable": False, "reason": reason},
            "model_results": {
                name: {"status": "not_evaluable", "reason": reason, "metrics": {}}
                for name in model_names
            },
            "comparison_deltas": {"M2_minus_M1_auroc": None, "M4_minus_M3_auroc": None, "M4_minus_M0_auroc": None},
        }

    trajectory_frame = trajectory_features.set_index("patient_id") if "patient_id" in trajectory_features.columns else trajectory_features.copy()
    static_features = static_features.copy()
    combined_features = static_features.join(trajectory_frame, how="left")

    static_reference_columns = [
        column
        for column in ["age", "sex", "encounter_count", "encounters_per_year", "history_days", "cohort_label"]
        if column in static_features.columns
    ]
    static_reference = static_features[static_reference_columns].copy()

    train_ids, test_ids = patient_level_split(patient_ids, test_size=test_size, random_state=random_state)
    if not test_ids or len(set(labels.loc[train_ids])) < 2 or len(set(labels.loc[test_ids])) < 2:
        reason = "Patient-level split did not produce both classes in train and test folds."
        return {
            "horizon_days": horizon_days,
            "viability": {"is_viable": False, "reason": reason},
            "model_results": {
                name: {"status": "not_evaluable", "reason": reason, "metrics": {}}
                for name in model_names
            },
            "comparison_deltas": {"M2_minus_M1_auroc": None, "M4_minus_M3_auroc": None, "M4_minus_M0_auroc": None},
        }

    models = {
        "M0": (LogisticRegression(max_iter=2000, class_weight="balanced"), static_reference),
        "M1": (
            LogisticRegression(
                penalty="elasticnet",
                solver="saga",
                l1_ratio=0.5,
                max_iter=4000,
                class_weight="balanced",
            ),
            static_features,
        ),
        "M2": (
            LogisticRegression(
                penalty="elasticnet",
                solver="saga",
                l1_ratio=0.5,
                max_iter=4000,
                class_weight="balanced",
            ),
            combined_features,
        ),
        "M3": (GradientBoostingClassifier(random_state=random_state), static_features),
        "M4": (GradientBoostingClassifier(random_state=random_state), combined_features),
    }

    model_results: dict[str, Any] = {}
    for model_name, (model, features) in models.items():
        filled = features.copy()
        X_train = filled.loc[train_ids]
        X_test = filled.loc[test_ids]
        y_train = labels.loc[train_ids]
        y_test = labels.loc[test_ids]
        model_results[model_name] = _fit_single_model(model_name, model, X_train, y_train, X_test, y_test)

    return {
        "horizon_days": horizon_days,
        "viability": {"is_viable": True, "reason": reason},
        "model_results": model_results,
        "comparison_deltas": model_comparison_deltas(model_results),
    }


def train_comparison_models(
    cohort: pd.DataFrame,
    participants: pd.DataFrame,
    encounters: pd.DataFrame,
    outcomes: pd.DataFrame,
    trajectory_features: pd.DataFrame,
    horizons: list[int],
    random_state: int = 42,
    test_size: float = 0.25,
) -> dict[str, Any]:
    """Train all comparison models across requested horizons."""

    static_features = _static_feature_frame(cohort, participants, encounters)
    label_map = _labels_by_horizon(cohort, outcomes, horizons)
    patient_ids = static_features.index.tolist()

    results: dict[str, Any] = {}
    for horizon in horizons:
        results[str(horizon)] = fit_horizon_model_suite(
            static_features=static_features,
            trajectory_features=trajectory_features,
            labels=label_map[horizon],
            patient_ids=patient_ids,
            horizon_days=horizon,
            random_state=random_state,
            test_size=test_size,
        )
    return results
