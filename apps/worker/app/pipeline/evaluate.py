"""Evaluation helpers for synthetic feasibility analyses.

Thresholds are intentionally conservative because this scaffold is synthetic and
research-only. Results should guide whether further synthetic experimentation is
worthwhile, not support clinical claims or deployment decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from app.pipeline.calibration import calibration_intercept_slope
from app.schemas import FeasibilityConclusion


@dataclass(frozen=True)
class FeasibilityDecision:
    """Research-only conclusion and the evidence used to reach it."""

    conclusion: FeasibilityConclusion
    reasons: list[str]


def bootstrap_ci(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    metric_fn: Any,
    n_bootstrap: int = 1000,
    ci: float = 0.95,
    random_state: int = 42,
) -> tuple[float, float]:
    """Return a percentile bootstrap CI for one prediction per patient."""

    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    if len(y_true) != len(y_prob):
        raise ValueError("y_true and y_prob must have the same length.")
    if not 0 < ci < 1:
        raise ValueError("ci must be between zero and one.")
    if len(y_true) == 0:
        return float("nan"), float("nan")

    rng = np.random.default_rng(random_state)
    scores: list[float] = []
    for _ in range(n_bootstrap):
        patient_indices = rng.integers(0, len(y_true), size=len(y_true))
        sample_y_true = y_true[patient_indices]
        if (
            metric_fn in (roc_auc_score, average_precision_score)
            and len(np.unique(sample_y_true)) < 2
        ):
            continue
        try:
            score = float(metric_fn(sample_y_true, y_prob[patient_indices]))
        except ValueError:
            # Some metrics are undefined for a sample with only one class.
            continue
        if np.isfinite(score):
            scores.append(score)

    if not scores:
        return float("nan"), float("nan")
    alpha = (1 - ci) / 2
    return tuple(float(value) for value in np.quantile(scores, [alpha, 1 - alpha]))


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
        "auroc_ci": [None, None],
        "auprc_ci": [None, None],
        "brier_ci": [None, None],
        "n_evaluable_patients": int(len(y_true)),
    }
    if len(y_true) == 0 or len(np.unique(y_true)) < 2:
        return metrics

    metrics["auroc"] = float(roc_auc_score(y_true, y_prob))
    metrics["auprc"] = float(average_precision_score(y_true, y_prob))
    metrics["brier_score"] = float(brier_score_loss(y_true, y_prob))
    for name, metric_fn in (
        ("auroc_ci", roc_auc_score),
        ("auprc_ci", average_precision_score),
        ("brier_ci", brier_score_loss),
    ):
        lower, upper = bootstrap_ci(y_true, y_prob, metric_fn)
        metrics[name] = [None, None] if np.isnan(lower) else [lower, upper]
    intercept, slope = calibration_intercept_slope(y_true, y_prob)
    metrics["calibration_intercept"] = intercept
    metrics["calibration_slope"] = slope
    return metrics


def subgroup_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    groups: Mapping[str, np.ndarray],
    min_group_size: int = 5,
) -> dict[str, dict[str, Any]]:
    """Return held-out subgroup metrics only for adequately sized, two-class groups."""

    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    if len(y_true) != len(y_prob):
        raise ValueError("y_true and y_prob must have the same length.")

    summaries: dict[str, dict[str, Any]] = {}
    for group_name, values in groups.items():
        values = np.asarray(values)
        if len(values) != len(y_true):
            raise ValueError(f"Group '{group_name}' must align with y_true.")

        for group_value in sorted(
            {str(value) for value in values if value is not None}
        ):
            mask = np.asarray([str(value) == group_value for value in values])
            subgroup_y_true = y_true[mask]
            if (
                len(subgroup_y_true) < min_group_size
                or len(np.unique(subgroup_y_true)) < 2
            ):
                continue
            summaries[f"{group_name}={group_value}"] = compute_metrics(
                subgroup_y_true, y_prob[mask]
            )

    return summaries


def model_comparison_deltas(
    metrics_by_model: dict[str, dict[str, Any]],
) -> dict[str, float | None]:
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
        "M5_trajectory_only_auroc": auroc("M5"),
        "M5_minus_M1_auroc": diff("M5", "M1"),
    }


def _finite_number(value: object) -> float | None:
    return (
        float(value) if isinstance(value, (int, float)) and np.isfinite(value) else None
    )


def _combined_model_results(result: dict[str, Any]) -> list[dict[str, Any]]:
    model_results = result.get("model_results", {})
    return [
        model_results[model_name]
        for model_name in ("M2", "M4")
        if model_results.get(model_name, {}).get("status") == "evaluated"
    ]


def _has_calibrated_combined_model(result: dict[str, Any]) -> bool:
    for model in _combined_model_results(result):
        slope = _finite_number(model.get("metrics", {}).get("calibration_slope"))
        if slope is not None and 0.8 <= slope <= 1.2:
            return True
    return False


def _has_stable_trajectory_features(result: dict[str, Any]) -> bool:
    model = result.get("model_results", {}).get("M2", {})
    stability = model.get("feature_stability", [])
    return any(
        _finite_number(item.get("selection_frequency")) is not None
        and _finite_number(item.get("direction_consistency")) is not None
        and float(item["selection_frequency"]) >= 0.6
        and float(item["direction_consistency"]) >= 0.8
        for item in stability
        if isinstance(item, dict)
    )


def _subgroups_are_not_concerning(result: dict[str, Any]) -> bool:
    model = result.get("model_results", {}).get("M2", {})
    subgroup_results = model.get("subgroup_metrics", {})
    if not subgroup_results:
        return True
    aurocs = [
        _finite_number(summary.get("auroc"))
        for summary in subgroup_results.values()
        if isinstance(summary, dict)
    ]
    return all(auroc is None or auroc >= 0.55 for auroc in aurocs)


def feasibility_decision(horizon_results: dict[str, Any]) -> FeasibilityDecision:
    """Apply conservative, research-only discrimination, calibration, and stability gates."""

    evaluable = [
        result
        for result in horizon_results.values()
        if any(
            model.get("status") == "evaluated"
            for model in result.get("model_results", {}).values()
        )
    ]
    if not evaluable:
        return FeasibilityDecision(
            FeasibilityConclusion.NOT_EVALUABLE,
            ["No horizon produced a reliable held-out model evaluation."],
        )

    best_aurocs: list[float] = []
    trajectory_uplifts: list[float] = []
    calibrated = False
    stable = False
    subgroup_safe = True
    for result in evaluable:
        aurocs = [
            _finite_number(model.get("metrics", {}).get("auroc"))
            for model in result.get("model_results", {}).values()
        ]
        best_aurocs.extend(score for score in aurocs if score is not None)
        for key in ("M2_minus_M1_auroc", "M4_minus_M3_auroc"):
            uplift = _finite_number(result.get("comparison_deltas", {}).get(key))
            if uplift is not None:
                trajectory_uplifts.append(uplift)
        calibrated = calibrated or _has_calibrated_combined_model(result)
        stable = stable or _has_stable_trajectory_features(result)
        subgroup_safe = subgroup_safe and _subgroups_are_not_concerning(result)

    best_auroc = max(best_aurocs, default=0.0)
    best_uplift = max(trajectory_uplifts, default=0.0)
    if best_auroc < 0.62:
        return FeasibilityDecision(
            FeasibilityConclusion.NO_GO,
            [
                "No evaluated model reached the minimum discrimination threshold for feasibility research."
            ],
        )

    blockers: list[str] = []
    if best_uplift < 0.03:
        blockers.append(
            "Combined trajectory models did not show the required incremental AUROC uplift over static baselines."
        )
    if not calibrated:
        blockers.append(
            "No combined model met the calibration slope gate of 0.80 to 1.20."
        )
    if not stable:
        blockers.append(
            "No trajectory feature met the development-only bootstrap stability gate."
        )
    if not subgroup_safe:
        blockers.append(
            "An adequately sized held-out subgroup showed concerning discrimination performance."
        )
    if blockers:
        return FeasibilityDecision(FeasibilityConclusion.REDIRECT, blockers)

    return FeasibilityDecision(
        FeasibilityConclusion.GO_FOR_EXTERNAL_VALIDATION,
        [
            "Combined trajectory models met discrimination, calibration, stability, and subgroup gates.",
            "This result is feasibility evidence only and requires independently governed external validation.",
        ],
    )


def feasibility_conclusion(horizon_results: dict[str, Any]) -> FeasibilityConclusion:
    """Return the compatibility conclusion from the full feasibility decision."""

    return feasibility_decision(horizon_results).conclusion
