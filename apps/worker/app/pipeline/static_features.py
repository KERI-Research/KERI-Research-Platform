"""Static (non-trajectory) per-variable measurement recency features.

Unlike full trajectory features (which require a minimum observation count to
compute slopes/deltas reliably), these lightweight features are computed for
every patient-variable pair with at least one observation strictly before the
feature cutoff: the last valid value observed, and the time elapsed between
that observation and the prediction anchor date.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def build_static_measurement_features(
    cohort: pd.DataFrame,
    observations: pd.DataFrame,
) -> pd.DataFrame:
    """Build last-value and recency features per patient-variable pair.

    Only observations strictly before each patient's ``feature_cutoff`` are
    used. Requires ``cohort`` to contain ``patient_id``, ``prediction_anchor_date``,
    and ``feature_cutoff`` columns.
    """

    if cohort.empty:
        return pd.DataFrame(columns=["patient_id"])

    index_cols = cohort[["patient_id", "prediction_anchor_date", "feature_cutoff"]].copy()
    index_cols["prediction_anchor_date"] = pd.to_datetime(index_cols["prediction_anchor_date"], utc=True, errors="coerce")
    index_cols["feature_cutoff"] = pd.to_datetime(index_cols["feature_cutoff"], utc=True, errors="coerce")

    wide_records: dict[str, dict[str, Any]] = {
        patient_id: {"patient_id": patient_id} for patient_id in index_cols["patient_id"].drop_duplicates().tolist()
    }

    if observations.empty:
        return pd.DataFrame(list(wide_records.values())).sort_values("patient_id").reset_index(drop=True)

    obs = observations.copy()
    obs["observed_at"] = pd.to_datetime(obs["observed_at"], utc=True, errors="coerce")
    eligible = obs.merge(index_cols, on="patient_id", how="inner")
    eligible = eligible.loc[eligible["observed_at"] < eligible["feature_cutoff"]].copy()

    if not eligible.empty:
        for (patient_id, variable_code), group in eligible.groupby(["patient_id", "variable_code"], sort=True):
            ordered = group.sort_values("observed_at")
            last_row = ordered.iloc[-1]
            prefix = f"static__{variable_code}__"
            record = wide_records.setdefault(patient_id, {"patient_id": patient_id})
            record[f"{prefix}last_value"] = float(last_row["value"])
            record[f"{prefix}days_since_last_measurement"] = float(
                (last_row["prediction_anchor_date"] - last_row["observed_at"]).total_seconds() / 86400.0
            )

    return pd.DataFrame(list(wide_records.values())).sort_values("patient_id").reset_index(drop=True)
