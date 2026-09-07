"""Evaluation helpers for synthetic feasibility analyses.

Thresholds are intentionally conservative because this scaffold is synthetic and
research-only. Results should guide whether further synthetic experimentation is
worthwhile, not support clinical claims or deployment decisions.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from app.pipeline.calibration import calibration_intercept_slope
from app.schemas import FeasibilityConclusion


def confidence_interval_hook(*_: Any, **__: Any) -> None:
    """Placeholder for future bootstrap confidence intervals."""

    return None


def feature_stability_hook(*_: Any, **__: Any) -> None:
    """Placeholder for future feature stability analysis."""

    return None


def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, Any]:
    """Compute discrimination and calibration metrics when class balance allows."""

    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    metrics: dict[str, Any] = {
        "auroc": None,
        "auprc": None,
        "brier_score": None,
        "calibration_intercept": None,
        "calibration_slope": None,
        "confidence_intervals": confidence_interval_hook(),
        "feature_stability": feature_stability_hook(),
    }
    if len(y_true) == 0 or len(np.unique(y_true)) < 2:
        return metrics

    metrics["auroc"] = float(roc_auc_score(y_true, y_prob))
    metrics["auprc"] = float(average_precision_score(y_true, y_prob))
    metrics["brier_score"] = float(brier_score_loss(y_true, y_prob))
    intercept, slope = calibration_intercept_slope(y_true, y_prob)
    metrics["calibration_intercept"] = intercept
    metrics["calibration_slope"] = slope
    return metrics


def model_comparison_deltas(metrics_by_model: dict[str, dict[str, Any]]) -> dict[str, float | None]:
    """Return selected AUROC deltas for trajectory-versus-static comparisons."""

    def auroc(model_name: str) -> float | None:
        metric = metrics_by_model.get(model_name, {})
        return metric.get("metrics", {}).get("auroc")

    def diff(a: str, b: str) -> float | None:
        a_score = auroc(a)
        b_score = auroc(b)
        if a_score is None or b_score is None:
            return None
        return float(a_score - b_score)

    return {
        "M2_minus_M1_auroc": diff("M2", "M1"),
        "M4_minus_M3_auroc": diff("M4", "M3"),
        "M4_minus_M0_auroc": diff("M4", "M0"),
    }


def feasibility_conclusion(horizon_results: dict[str, Any]) -> FeasibilityConclusion:
    """Derive a conservative research feasibility conclusion.

    GO: at least one evaluable horizon has a best-model AUROC >= 0.70 and a
    trajectory uplift >= 0.03.
    REDIRECT: evaluable but trajectory uplift is weak while some signal exists.
    NO_GO: evaluable but signals are weak or inconsistent.
    NOT_EVALUABLE: no horizon produced reliable evaluable outputs.
    """

    evaluable = []
    for result in horizon_results.values():
        model_results = result.get("model_results", {})
        if any(model.get("status") == "evaluated" for model in model_results.values()):
            evaluable.append(result)

    if not evaluable:
        return FeasibilityConclusion.NOT_EVALUABLE

    best_aurocs: list[float] = []
    uplifts: list[float] = []
    for result in evaluable:
        aurocs = [
            model.get("metrics", {}).get("auroc")
            for model in result.get("model_results", {}).values()
            if model.get("metrics", {}).get("auroc") is not None
        ]
        if aurocs:
            best_aurocs.append(max(aurocs))
        for key in ("M2_minus_M1_auroc", "M4_minus_M3_auroc", "M4_minus_M0_auroc"):
            value = result.get("comparison_deltas", {}).get(key)
            if value is not None:
                uplifts.append(value)

    best_auroc = max(best_aurocs) if best_aurocs else 0.0
    best_uplift = max(uplifts) if uplifts else 0.0
    if best_auroc >= 0.70 and best_uplift >= 0.03:
        return FeasibilityConclusion.GO
    if best_auroc >= 0.62:
        return FeasibilityConclusion.REDIRECT
    return FeasibilityConclusion.NO_GO
