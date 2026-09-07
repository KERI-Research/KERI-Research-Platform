"""Trajectory feature engineering with strict pre-cutoff leakage controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import linregress, theilslopes


@dataclass
class TrajectoryFeatures:
    """Wide feature matrix and accompanying feature-manifest metadata."""

    features: pd.DataFrame
    feature_manifest: list[dict[str, Any]]


def _safe_relative_change(first_value: float, last_value: float) -> float | None:
    if abs(first_value) < 1e-12:
        return None
    return float((last_value - first_value) / abs(first_value))


def _direction_consistency(values: np.ndarray) -> float | None:
    if len(values) < 2:
        return None
    deltas = np.diff(values)
    non_zero = deltas[np.abs(deltas) > 1e-12]
    if len(non_zero) == 0:
        return 1.0
    signs = np.sign(non_zero)
    majority_sign = 1 if np.sum(signs > 0) >= np.sum(signs < 0) else -1
    return float(np.mean(signs == majority_sign))


def _resolve_unit(dictionary_entry: dict[str, Any], ordered: pd.DataFrame) -> str | None:
    if dictionary_entry.get("unit"):
        return str(dictionary_entry["unit"])
    if "unit" in ordered.columns and ordered["unit"].notna().any():
        return str(ordered["unit"].dropna().iloc[0])
    return None


def build_trajectory_features(
    cohort: pd.DataFrame,
    observations: pd.DataFrame,
    data_dictionary: pd.DataFrame,
    min_observations_per_variable: int,
) -> TrajectoryFeatures:
    """Build per-patient trajectory features from observations strictly before feature cutoff."""

    if cohort.empty or observations.empty:
        return TrajectoryFeatures(features=pd.DataFrame(columns=["patient_id"]), feature_manifest=[])

    lookup = data_dictionary.set_index("variable_code").to_dict("index") if not data_dictionary.empty else {}

    index_cols = cohort[["patient_id", "prediction_anchor_date", "feature_cutoff"]].copy()
    index_cols["prediction_anchor_date"] = pd.to_datetime(index_cols["prediction_anchor_date"], utc=True, errors="coerce")
    index_cols["feature_cutoff"] = pd.to_datetime(index_cols["feature_cutoff"], utc=True, errors="coerce")

    obs = observations.copy()
    obs["observed_at"] = pd.to_datetime(obs["observed_at"], utc=True, errors="coerce")
    eligible = obs.merge(index_cols, on="patient_id", how="inner")
    eligible = eligible.loc[eligible["observed_at"] < eligible["feature_cutoff"]].copy()
    if eligible.empty:
        return TrajectoryFeatures(features=index_cols[["patient_id"]].drop_duplicates().reset_index(drop=True), feature_manifest=[])

    wide_records: dict[str, dict[str, Any]] = {
        patient_id: {"patient_id": patient_id}
        for patient_id in index_cols["patient_id"].drop_duplicates().tolist()
    }
    feature_manifest: list[dict[str, Any]] = []

    for (patient_id, variable_code), group in eligible.groupby(["patient_id", "variable_code"], sort=True):
        ordered = group.sort_values("observed_at").reset_index(drop=True)
        if len(ordered) < min_observations_per_variable:
            continue

        timestamps = ordered["observed_at"]
        values = ordered["value"].astype(float).to_numpy()
        days = (timestamps - timestamps.iloc[0]).dt.total_seconds().to_numpy() / 86400.0
        first_value = float(values[0])
        last_value = float(values[-1])
        mean_value = float(np.mean(values))
        median_value = float(np.median(values))
        span_days = float(max(days[-1] - days[0], 0.0)) if len(days) > 1 else 0.0
        split_idx = max(1, len(values) // 2)
        historic_values = values[:split_idx]
        recent_values = values[split_idx:]
        baseline = float(np.mean(values[:-1])) if len(values) > 1 else first_value
        deviations = values - mean_value
        robust_slope = None
        acceleration = None
        ols_slope = None

        if len(values) >= 2 and not np.allclose(days, days[0]):
            ols_slope = float(linregress(days, values).slope)
            robust_slope = float(theilslopes(values, days)[0])
        if len(values) >= 3 and np.unique(days).size >= 3:
            quadratic = np.polyfit(days, values, deg=2)
            acceleration = float(2.0 * quadratic[0])

        prefix = f"traj__{variable_code}__"
        record = wide_records.setdefault(patient_id, {"patient_id": patient_id})
        record.update(
            {
                f"{prefix}first": first_value,
                f"{prefix}last": last_value,
                f"{prefix}absolute_change": float(last_value - first_value),
                f"{prefix}relative_change": _safe_relative_change(first_value, last_value),
                f"{prefix}ols_slope": ols_slope,
                f"{prefix}robust_slope": robust_slope,
                f"{prefix}recent_vs_historic_mean_delta": float(np.mean(recent_values) - np.mean(historic_values)) if len(recent_values) else 0.0,
                f"{prefix}personal_baseline_deviation": float(last_value - baseline),
                f"{prefix}max_deviation": float(np.max(np.abs(deviations))),
                f"{prefix}variation_range": float(np.max(values) - np.min(values)),
                f"{prefix}variation_std": float(np.std(values, ddof=0)),
                f"{prefix}observation_count": int(len(values)),
                f"{prefix}direction_consistency": _direction_consistency(values),
                f"{prefix}acceleration": acceleration,
                f"{prefix}measurement_density_per_day": float(len(values) / max(span_days, 1.0)),
                f"{prefix}time_since_last_observation_days": float((ordered['prediction_anchor_date'].iloc[0] - timestamps.iloc[-1]).total_seconds() / 86400.0),
                f"{prefix}mean": mean_value,
                f"{prefix}median": median_value,
            }
        )

        dictionary_entry = lookup.get(variable_code, {})
        feature_manifest.append(
            {
                "patient_id": patient_id,
                "source_variable": variable_code,
                "unit": _resolve_unit(dictionary_entry, ordered),
                "window": {
                    "start": timestamps.iloc[0].isoformat(),
                    "end": timestamps.iloc[-1].isoformat(),
                },
                "method": [
                    "first_last_summary",
                    "ols_slope",
                    "theil_sen_slope",
                    "historic_recent_delta",
                    "direction_consistency",
                    "acceleration_if_available",
                ],
                "source_timestamps_used": [timestamp.isoformat() for timestamp in timestamps.tolist()],
            }
        )

    features = pd.DataFrame(list(wide_records.values())).sort_values("patient_id").reset_index(drop=True)
    return TrajectoryFeatures(features=features, feature_manifest=feature_manifest)
