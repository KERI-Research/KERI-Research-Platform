import numpy as np
from sklearn.metrics import roc_auc_score

from app.pipeline.evaluate import bootstrap_ci, compute_metrics


def test_bootstrap_ci_is_repeatable_for_patient_level_predictions() -> None:
    y_true = np.array([0, 0, 0, 1, 1, 1])
    y_prob = np.array([0.1, 0.2, 0.4, 0.6, 0.8, 0.9])

    first = bootstrap_ci(y_true, y_prob, roc_auc_score, n_bootstrap=100, random_state=7)
    second = bootstrap_ci(y_true, y_prob, roc_auc_score, n_bootstrap=100, random_state=7)

    assert first == second
    assert first[0] <= first[1]


def test_compute_metrics_includes_bootstrap_confidence_intervals() -> None:
    metrics = compute_metrics(
        np.array([0, 0, 0, 1, 1, 1]),
        np.array([0.1, 0.2, 0.4, 0.6, 0.8, 0.9]),
    )

    for metric_name in ("auroc_ci", "auprc_ci", "brier_ci"):
        lower, upper = metrics[metric_name]
        assert lower is not None
        assert upper is not None
        assert lower <= upper
