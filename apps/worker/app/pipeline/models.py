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

from app.pipeline.cohort import compute_first_history_at
from app.pipeline.evaluate import compute_metrics, model_comparison_deltas
from app.pipeline.index_dates import build_horizon_frame
from app.pipeline.splits import patient_level_split
from app.pipeline.static_features import build_static_measurement_features
from app.pipeline.trajectories import build_trajectory_features

MIN_SUFFICIENT_HISTORY_PATIENTS = 20
MIN_HISTORY_MULTIPLIER = 2

# Static (non-outcome-derived) participant/encounter columns that are safe to
# feed into models. Any date, label, treatment, or cohort-assignment column
# must never appear here: those are outcome-derived or directly leak case
# status (for example `cohort_label`, `diagnosis_date`, `reference_date`).
ALLOWED_STATIC_REFERENCE_COLUMNS = ["age", "sex", "encounter_count", "encounters_per_year", "history_days"]


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
    observations: pd.DataFrame,
) -> pd.DataFrame:
    """Build non-outcome-derived static features strictly before feature_cutoff.

    Only demographic/utilisation fields and per-variable last-value/recency
    features are included. Outcome-derived fields (``cohort_label``,
    ``diagnosis_date``, ``reference_date``, labels, incident flags, and
    treatment-related fields) must never enter this frame.
    """

    participant_frame = participants[["patient_id"]].copy()
    if "age" in participants.columns:
        participant_frame["age"] = participants["age"]
    if "sex" in participants.columns:
        participant_frame["sex"] = participants["sex"]

    static = cohort[["patient_id", "feature_cutoff", "history_days"]].copy()
    static = static.merge(participant_frame, on="patient_id", how="left")

    encounter_frame = encounters.copy()
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
    static["encounters_per_year"] = static["encounter_count"] / np.maximum(static["history_days"] / 365.0, 1e-6)
    static = static.drop(columns=["feature_cutoff"])

    measurement_features = build_static_measurement_features(cohort, observations)
    static = static.merge(measurement_features, on="patient_id", how="left")

    return static.set_index("patient_id")


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


def _not_evaluable_result(horizon_days: int, reason: str) -> dict[str, Any]:
    model_names = ["M0", "M1", "M2", "M3", "M4"]
    return {
        "horizon_days": horizon_days,
        "viability": {"is_viable": False, "reason": reason},
        "model_results": {name: {"status": "not_evaluable", "reason": reason, "metrics": {}} for name in model_names},
        "comparison_deltas": {"M2_minus_M1_auroc": None, "M4_minus_M3_auroc": None, "M4_minus_M0_auroc": None},
        "cohort_size": 0,
        "exclusions": {},
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

    static_reference_columns = [column for column in ALLOWED_STATIC_REFERENCE_COLUMNS if column in static_features.columns]
    static_reference = static_features[static_reference_columns].copy()

    train_ids, test_ids = patient_level_split(
        patient_ids,
        test_size=test_size,
        random_state=random_state,
        labels=labels.to_dict(),
    )
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
    participants: pd.DataFrame,
    observations: pd.DataFrame,
    outcomes: pd.DataFrame,
    encounters: pd.DataFrame,
    data_dictionary: pd.DataFrame,
    horizons: list[int],
    prediction_gap_days: int,
    min_history_days: int,
    min_observations_per_variable: int,
    random_state: int = 42,
    test_size: float = 0.25,
) -> tuple[dict[str, Any], dict[str, dict[str, int]], dict[str, int], list[dict[str, Any]]]:
    """Train all comparison models across requested horizons.

    Builds a distinct, horizon-specific analysis frame (prediction anchor,
    feature cutoff, and label) for every horizon, so that features and labels
    can never leak across horizons or use post-anchor information.

    Returns ``(results_by_horizon, exclusions_by_horizon, cohort_size_by_horizon,
    feature_manifest)``.
    """

    first_history = compute_first_history_at(observations, encounters)

    results: dict[str, Any] = {}
    exclusions_by_horizon: dict[str, dict[str, int]] = {}
    cohort_size_by_horizon: dict[str, int] = {}
    feature_manifest: list[dict[str, Any]] = []

    for horizon in horizons:
        horizon_key = str(horizon)
        cohort, exclusions = build_horizon_frame(
            participants=participants,
            outcomes=outcomes,
            first_history=first_history,
            horizon_days=horizon,
            prediction_gap_days=prediction_gap_days,
            min_history_days=min_history_days,
        )
        exclusions_by_horizon[horizon_key] = exclusions
        cohort_size_by_horizon[horizon_key] = int(len(cohort))

        if cohort.empty:
            results[horizon_key] = _not_evaluable_result(horizon, "No eligible patients for this horizon.")
            continue

        trajectory_bundle = build_trajectory_features(
            cohort=cohort,
            observations=observations,
            data_dictionary=data_dictionary,
            min_observations_per_variable=min_observations_per_variable,
        )
        for entry in trajectory_bundle.feature_manifest:
            feature_manifest.append({**entry, "horizon_days": horizon})

        static_features = _static_feature_frame(cohort, participants, encounters, observations)
        labels = cohort.set_index("patient_id")["label"]
        patient_ids = cohort["patient_id"].tolist()

        result = fit_horizon_model_suite(
            static_features=static_features,
            trajectory_features=trajectory_bundle.features,
            labels=labels,
            patient_ids=patient_ids,
            horizon_days=horizon,
            random_state=random_state,
            test_size=test_size,
        )
        result["cohort_size"] = int(len(cohort))
        result["exclusions"] = exclusions
        results[horizon_key] = result

    return results, exclusions_by_horizon, cohort_size_by_horizon, feature_manifest
