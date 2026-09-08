from app.pipeline.reporting import render_html_report, render_model_card


def test_report_templates_render_required_research_content() -> None:
    result = {
        "job_id": "job-1",
        "dataset_id": "dataset-1",
        "schema_version": "1",
        "run_date": "2026-09-07T00:00:00+00:00",
        "configuration_hash": "abc123",
        "analysis_decisions": {
            "requested_horizons": [365],
            "feasibility_conclusion": "NO_GO",
        },
        "cohort_flow": {
            "eligible_cohort_size_by_horizon": {"365": 20},
            "exclusions_by_horizon": {"365": {"insufficient_history": 2}},
        },
        "metrics_per_model_horizon": {
            "365": {
                "comparison_deltas": {
                    "M2_minus_M1_auroc": 0.01,
                    "M4_minus_M3_auroc": 0.02,
                },
                "model_results": {
                    "M0": {"status": "evaluated", "metrics": {}},
                    "M1": {"status": "evaluated", "metrics": {}},
                    "M2": {"status": "evaluated", "metrics": {}},
                    "M3": {"status": "evaluated", "metrics": {}},
                    "M4": {"status": "evaluated", "metrics": {}, "shap_summary": []},
                },
            }
        },
        "limitations": ["Synthetic data only."],
    }

    model_card = render_model_card(result)
    html_report = render_html_report(result)

    assert "Research use only — non-diagnostic" in model_card
    assert "pseudonymised data" in model_card
    assert "Research use only — non-diagnostic" in html_report
    assert "Static versus longitudinal comparison" in html_report
