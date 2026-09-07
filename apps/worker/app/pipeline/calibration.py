"""Calibration helpers for research-only model summaries."""

from __future__ import annotations

import numpy as np
from numpy.linalg import LinAlgError
from sklearn.linear_model import LogisticRegression


def calibration_intercept_slope(
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> tuple[float | None, float | None]:
    """Estimate calibration intercept and slope when feasible.

    Returns `(None, None)` when the estimate is unstable or not computable.
    """

    try:
        y_true = np.asarray(y_true)
        y_prob = np.asarray(y_prob)
        if len(y_true) < 10 or len(np.unique(y_true)) < 2:
            return None, None
        clipped = np.clip(y_prob, 1e-6, 1 - 1e-6)
        logits = np.log(clipped / (1 - clipped)).reshape(-1, 1)
        model = LogisticRegression(C=1e6, max_iter=1000, class_weight=None)
        model.fit(logits, y_true)
        return float(model.intercept_[0]), float(model.coef_[0][0])
    except (ValueError, TypeError, FloatingPointError, LinAlgError):
        return None, None
