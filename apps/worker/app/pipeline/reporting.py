"""Research-only JSON and Markdown reporting utilities."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.schemas import AnalysisConfig, FeasibilityConclusion

DISCLAIMER = (
    "Research use only. Synthetic data only. Non-diagnostic. "
    "Not clinically validated and not for patient-care decisions."
)


def _configuration_hash(config: AnalysisConfig) -> str:
    payload = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_report_payload(
    *,
    job_id: str,
    config: AnalysisConfig,
    cohort_size: int,
    exclusions: dict[str, int],
    horizon_results: dict[str, Any],
    feasibility: FeasibilityConclusion,
    feature_manifest: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a structured report dictionary from pipeline outputs."""

    return {
        "job_id": job_id,
        "dataset_provenance": {
            "synthetic_only": True,
            "description": "Inline synthetic scaffold payload for longitudinal feasibility research.",
        },
        "configuration_hash": _configuration_hash(config),
        "cohort_flow": {
            "eligible_cohort_size": cohort_size,
            "exclusions": exclusions,
        },
        "analysis_decisions": {
            "prediction_gap_days": config.prediction_gap_days,
            "min_history_days": config.min_history_days,
            "min_observations_per_variable": config.min_observations_per_variable,
            "requested_horizons": config.horizons,
            "feasibility_conclusion": feasibility.value,
        },
        "metrics_per_model_horizon": horizon_results,
        "trajectory_vs_static_comparison": {
            horizon: result.get("comparison_deltas", {})
            for horizon, result in horizon_results.items()
        },
        "feature_manifest": feature_manifest,
        "limitations": [
            "Synthetic scaffold only; discrimination and calibration are not clinically meaningful.",
            "In-memory job storage is not durable.",
            "No external validation, drift monitoring, or decision-impact analysis is performed.",
        ],
        "disclaimer": DISCLAIMER,
    }


def build_markdown_report(report: dict[str, Any]) -> str:
    """Create a model-card-style Markdown report from the JSON report payload."""

    lines = [
        "# ORAMA Synthetic Research Worker Report",
        "",
        f"> **{DISCLAIMER}**",
        "",
        "## Dataset provenance",
        f"- Synthetic only: {report['dataset_provenance']['synthetic_only']}",
        f"- Description: {report['dataset_provenance']['description']}",
        "",
        "## Cohort flow",
        f"- Eligible cohort size: {report['cohort_flow']['eligible_cohort_size']}",
    ]
    for reason, count in report["cohort_flow"]["exclusions"].items():
        lines.append(f"- Excluded ({reason}): {count}")

    lines.extend(
        [
            "",
            "## Analysis decisions",
            f"- Configuration hash: `{report['configuration_hash']}`",
            f"- Feasibility conclusion: **{report['analysis_decisions']['feasibility_conclusion']}**",
            f"- Prediction gap days: {report['analysis_decisions']['prediction_gap_days']}",
            f"- Minimum history days: {report['analysis_decisions']['min_history_days']}",
            f"- Minimum observations per variable: {report['analysis_decisions']['min_observations_per_variable']}",
            "",
            "## Horizon results",
        ]
    )

    for horizon, result in report["metrics_per_model_horizon"].items():
        lines.append(f"### Horizon {horizon} days")
        viability = result.get("viability", {})
        lines.append(f"- Viable: {viability.get('is_viable')}")
        lines.append(f"- Viability note: {viability.get('reason')}")
        for model_name, model_result in result.get("model_results", {}).items():
            metrics = model_result.get("metrics", {})
            lines.append(
                f"- {model_name}: status={model_result.get('status')}, "
                f"AUROC={metrics.get('auroc')}, AUPRC={metrics.get('auprc')}, Brier={metrics.get('brier_score')}"
            )
        deltas = result.get("comparison_deltas", {})
        lines.append(f"- Trajectory deltas: {deltas}")
        lines.append("")

    lines.extend(
        [
            "## Limitations",
            *[f"- {item}" for item in report["limitations"]],
            "",
            f"> **{report['disclaimer']}**",
        ]
    )
    return "\n".join(lines)
