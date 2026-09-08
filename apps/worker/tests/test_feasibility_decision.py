from app.pipeline.evaluate import feasibility_decision
from app.schemas import FeasibilityConclusion


def _horizon_result(
    *, auroc: float, uplift: float, slope: float | None, stable: bool
) -> dict:
    stability = (
        [{"selection_frequency": 0.8, "direction_consistency": 0.9}] if stable else []
    )
    return {
        "model_results": {
            "M1": {"status": "evaluated", "metrics": {"auroc": auroc - uplift}},
            "M2": {
                "status": "evaluated",
                "metrics": {"auroc": auroc, "calibration_slope": slope},
                "feature_stability": stability,
            },
            "M3": {"status": "evaluated", "metrics": {"auroc": auroc - uplift}},
            "M4": {
                "status": "evaluated",
                "metrics": {"auroc": auroc, "calibration_slope": slope},
            },
        },
        "comparison_deltas": {"M2_minus_M1_auroc": uplift, "M4_minus_M3_auroc": uplift},
    }


def test_positive_decision_requires_external_validation_label() -> None:
    decision = feasibility_decision(
        {"365": _horizon_result(auroc=0.75, uplift=0.05, slope=0.95, stable=True)}
    )

    assert decision.conclusion == FeasibilityConclusion.GO_FOR_EXTERNAL_VALIDATION
    assert any("external validation" in reason.lower() for reason in decision.reasons)


def test_missing_calibration_or_stability_redirects_research() -> None:
    decision = feasibility_decision(
        {"365": _horizon_result(auroc=0.75, uplift=0.05, slope=None, stable=False)}
    )

    assert decision.conclusion == FeasibilityConclusion.REDIRECT
    assert len(decision.reasons) == 2
