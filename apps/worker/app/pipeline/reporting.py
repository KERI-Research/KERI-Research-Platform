"""Research-only JSON and Markdown reporting utilities."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from app.schemas import AnalysisConfig, FeasibilityConclusion

DISCLAIMER = (
    "Research use only. Synthetic data only. Non-diagnostic. "
    "Not clinically validated and not for patient-care decisions."
)
TEMPLATES_DIRECTORY = Path(__file__).parent.parent / "templates"


def compute_shap_summary(
    fitted_model: Any, X_test: Any
) -> list[dict[str, float | str]]:
    """Return M4's top test-set feature importances when SHAP is installed."""

    try:
        import shap
    except ImportError:
        return []

    preprocessor = fitted_model.named_steps["preprocessor"]
    model = fitted_model.named_steps["model"]
    shap_values = shap.TreeExplainer(model).shap_values(preprocessor.transform(X_test))
    if isinstance(shap_values, list):
        shap_values = shap_values[-1]
    mean_abs_shap = abs(shap_values).mean(axis=0)
    feature_names = preprocessor.get_feature_names_out()
    ranked = sorted(
        zip(feature_names, mean_abs_shap), key=lambda item: item[1], reverse=True
    )[:20]
    return [
        {"feature": str(feature), "mean_abs_shap": float(value)}
        for feature, value in ranked
    ]


def _template_context(result: dict[str, Any]) -> dict[str, Any]:
    decisions = result.get("analysis_decisions", {})
    results_by_horizon = result.get(
        "results_by_horizon", result.get("metrics_per_model_horizon", {})
    )
    return {
        "job_id": result.get("job_id"),
        "dataset_id": result.get("dataset_id", "inline-synthetic-dataset"),
        "schema_version": result.get("schema_version", "0.1"),
        "run_date": result.get("run_date", datetime.now(timezone.utc).isoformat()),
        "horizons": decisions.get("requested_horizons", list(results_by_horizon)),
        "model_names": ["M0", "M1", "M2", "M3", "M4", "M5"],
        "decision": decisions.get(
            "feasibility_conclusion", result.get("decision", "NOT_EVALUABLE")
        ),
        "decision_reasons": result.get(
            "decision_reasons", result.get("limitations", [])
        ),
        "results_by_horizon": results_by_horizon,
        "cohort_flow": result.get("cohort_flow", {}),
        "configuration_hash": result.get("configuration_hash"),
    }


def _render_template(template_name: str, result: dict[str, Any]) -> str:
    environment = Environment(
        loader=FileSystemLoader(TEMPLATES_DIRECTORY),
        autoescape=template_name.endswith(".html.j2"),
    )
    return environment.get_template(template_name).render(**_template_context(result))


def render_model_card(result: dict[str, Any]) -> str:
    """Render the Markdown model card from a report payload."""

    return _render_template("model_card.md.j2", result)


def render_html_report(result: dict[str, Any]) -> str:
    """Render the HTML research report from a report payload."""

    return _render_template("report.html.j2", result)


def _configuration_hash(config: AnalysisConfig) -> str:
    payload = json.dumps(
        config.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_report_payload(
    *,
    job_id: str,
    dataset_id: str | None,
    config: AnalysisConfig,
    cohort_size_by_horizon: dict[str, int],
    exclusions_by_horizon: dict[str, dict[str, int]],
    horizon_results: dict[str, Any],
    feasibility: FeasibilityConclusion,
    decision_reasons: list[str],
    feature_manifest: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a structured report dictionary from pipeline outputs.

    Cohort size and exclusions are horizon-specific: each horizon uses its own
    prediction-anchor date and therefore its own eligible analysis population.
    """

    return {
        "job_id": job_id,
        "dataset_id": dataset_id or "inline-synthetic-dataset",
        "dataset_provenance": {
            "synthetic_only": True,
            "description": (
                "Private synthetic research dataset object for longitudinal feasibility research."
                if dataset_id
                else "Inline synthetic scaffold payload for longitudinal feasibility research."
            ),
        },
        "configuration_hash": _configuration_hash(config),
        "cohort_flow": {
            "eligible_cohort_size_by_horizon": cohort_size_by_horizon,
            "exclusions_by_horizon": exclusions_by_horizon,
        },
        "analysis_decisions": {
            "prediction_gap_days": config.prediction_gap_days,
            "min_history_days": config.min_history_days,
            "min_observations_per_variable": config.min_observations_per_variable,
            "requested_horizons": config.horizons,
            "feasibility_conclusion": feasibility.value,
            "decision_reasons": decision_reasons,
            "external_validation_required": feasibility
            == FeasibilityConclusion.GO_FOR_EXTERNAL_VALIDATION,
        },
        "decision_reasons": decision_reasons,
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
    ]
    for horizon, size in report["cohort_flow"][
        "eligible_cohort_size_by_horizon"
    ].items():
        lines.append(f"- Horizon {horizon} days eligible cohort size: {size}")
    for horizon, exclusions in report["cohort_flow"]["exclusions_by_horizon"].items():
        for reason, count in exclusions.items():
            lines.append(f"- Horizon {horizon} days excluded ({reason}): {count}")

    lines.extend(
        [
            "",
            "## Analysis decisions",
            f"- Configuration hash: `{report['configuration_hash']}`",
            f"- Feasibility conclusion: **{report['analysis_decisions']['feasibility_conclusion']}**",
            *[
                f"- Decision reason: {reason}"
                for reason in report["analysis_decisions"]["decision_reasons"]
            ],
            f"- External validation required: {report['analysis_decisions']['external_validation_required']}",
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
