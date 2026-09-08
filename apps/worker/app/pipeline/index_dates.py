"""Horizon-specific prediction-anchor and label computation.

Each requested horizon gets its own analysis frame instead of a single shared
"index date". This avoids a critical leakage bug where using the outcome date
itself as the index date makes every case positive at day 0 for every horizon.

For a horizon of ``H`` days:

- **Cases** (patients with a recorded outcome) receive
  ``prediction_anchor_date = earliest_outcome_at - H days``. The outcome
  therefore occurs strictly after the anchor and exactly at the boundary of
  the horizon window, so the positive label is only ever assigned when the
  outcome genuinely falls within ``(anchor, anchor + H]``.
- **Controls** (patients with no recorded outcome at all) receive
  ``prediction_anchor_date`` from their own eligible follow-up/reference time
  (``reference_date``, falling back to ``diagnosis_date`` when present).
  Because they have no outcome, they are always negative for every horizon,
  and are defensively excluded (never silently mislabeled) if any outcome is
  ever found inside their horizon window.

``feature_cutoff = prediction_anchor_date - prediction_gap_days`` is the
strict boundary before which every static, encounter, and trajectory feature
must be derived.
"""

from __future__ import annotations

import pandas as pd


def _earliest_outcome_dates(outcomes: pd.DataFrame) -> pd.DataFrame:
    if outcomes.empty:
        return pd.DataFrame(columns=["patient_id", "outcome_at"])
    frame = outcomes.copy()
    frame["outcome_at"] = pd.to_datetime(frame["outcome_at"], utc=True, errors="coerce")
    return (
        frame.dropna(subset=["outcome_at"])
        .groupby("patient_id", as_index=False)["outcome_at"]
        .min()
    )


def build_horizon_frame(
    participants: pd.DataFrame,
    outcomes: pd.DataFrame,
    first_history: pd.DataFrame,
    horizon_days: int,
    prediction_gap_days: int,
    min_history_days: int,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Build the eligible, labelled analysis frame for a single horizon.

    Returns a frame with columns ``[patient_id, label, is_case,
    prediction_anchor_date, feature_cutoff, history_days]`` containing only
    patients eligible for this horizon, plus a dictionary of exclusion-reason
    counts specific to this horizon.
    """

    exclusions = {
        "no_valid_anchor": 0,
        "outcome_before_or_at_anchor": 0,
        "control_outcome_within_horizon": 0,
        "missing_history": 0,
        "insufficient_history": 0,
    }

    if participants.empty:
        empty = pd.DataFrame(
            columns=[
                "patient_id",
                "label",
                "is_case",
                "prediction_anchor_date",
                "feature_cutoff",
                "history_days",
            ]
        )
        return empty, exclusions

    def _as_utc_datetime_column(values: pd.Series) -> pd.Series:
        converted = pd.to_datetime(values, utc=True, errors="coerce")
        if converted.dt.tz is None:
            converted = converted.dt.tz_localize("UTC")
        return converted

    base = participants[["patient_id"]].copy()
    base["reference_date"] = (
        _as_utc_datetime_column(participants["reference_date"])
        if "reference_date" in participants.columns
        else pd.Series(pd.NaT, index=base.index, dtype="datetime64[ns, UTC]")
    )
    base["diagnosis_date_fallback"] = (
        _as_utc_datetime_column(participants["diagnosis_date"])
        if "diagnosis_date" in participants.columns
        else pd.Series(pd.NaT, index=base.index, dtype="datetime64[ns, UTC]")
    )

    all_outcomes = outcomes.copy()
    if not all_outcomes.empty:
        all_outcomes["outcome_at"] = pd.to_datetime(
            all_outcomes["outcome_at"], utc=True, errors="coerce"
        )

    earliest_outcome = _earliest_outcome_dates(outcomes)
    base = base.merge(earliest_outcome, on="patient_id", how="left")
    base["is_case"] = base["outcome_at"].notna()

    horizon_delta = pd.to_timedelta(horizon_days, unit="D")
    gap_delta = pd.to_timedelta(prediction_gap_days, unit="D")

    case_mask = base["is_case"]
    control_reference = base["reference_date"].where(
        base["reference_date"].notna(), base["diagnosis_date_fallback"]
    )
    anchor = pd.Series(pd.NaT, index=base.index, dtype="datetime64[ns, UTC]")
    if case_mask.any():
        anchor.loc[case_mask] = base.loc[case_mask, "outcome_at"] - horizon_delta
    if (~case_mask).any():
        anchor.loc[~case_mask] = control_reference.loc[~case_mask]
    base["prediction_anchor_date"] = anchor

    missing_anchor = base["prediction_anchor_date"].isna()
    exclusions["no_valid_anchor"] = int(missing_anchor.sum())
    base = base.loc[~missing_anchor].copy()

    empty_result_columns = [
        "patient_id",
        "label",
        "is_case",
        "prediction_anchor_date",
        "feature_cutoff",
        "history_days",
    ]
    if base.empty:
        return pd.DataFrame(columns=empty_result_columns), exclusions

    if not all_outcomes.empty and not base.empty:
        # Defensive check: no eligible patient may have any recorded outcome
        # at or before their own prediction anchor. For genuine cases this is
        # impossible by construction (anchor = outcome_at - horizon, and
        # horizon > 0), but the check guards against duplicate/earlier
        # outcome rows making the anchor effectively post-event.
        merged = base[["patient_id", "prediction_anchor_date"]].merge(
            all_outcomes[["patient_id", "outcome_at"]], on="patient_id", how="inner"
        )
        prior_or_at_anchor = merged.loc[
            merged["outcome_at"] <= merged["prediction_anchor_date"], "patient_id"
        ]
        bad_ids = set(prior_or_at_anchor.unique())
        if bad_ids:
            exclusions["outcome_before_or_at_anchor"] = len(bad_ids)
            base = base.loc[~base["patient_id"].isin(bad_ids)].copy()

    if not all_outcomes.empty and not base.empty:
        # Defensive check: a patient without their own recorded outcome must
        # never be silently used as a negative example if some outcome
        # falls inside their horizon window. Excluded rather than relabeled.
        control_rows = base.loc[
            ~base["is_case"], ["patient_id", "prediction_anchor_date"]
        ]
        if not control_rows.empty:
            merged_controls = control_rows.merge(
                all_outcomes[["patient_id", "outcome_at"]], on="patient_id", how="inner"
            )
            if not merged_controls.empty:
                merged_controls["days_to_outcome"] = (
                    merged_controls["outcome_at"]
                    - merged_controls["prediction_anchor_date"]
                ).dt.days
                offending = merged_controls.loc[
                    (merged_controls["days_to_outcome"] > 0)
                    & (merged_controls["days_to_outcome"] <= horizon_days),
                    "patient_id",
                ].unique()
                if len(offending):
                    exclusions["control_outcome_within_horizon"] = int(len(offending))
                    base = base.loc[~base["patient_id"].isin(offending)].copy()

    if base.empty:
        return pd.DataFrame(columns=empty_result_columns), exclusions

    base["feature_cutoff"] = base["prediction_anchor_date"] - gap_delta

    base = base.merge(first_history, on="patient_id", how="left")
    exclusions["missing_history"] = int(base["first_history_at"].isna().sum())
    base = base.dropna(subset=["first_history_at"]).copy()

    if base.empty:
        return pd.DataFrame(columns=empty_result_columns), exclusions

    base["history_days"] = (
        base["prediction_anchor_date"] - base["first_history_at"]
    ).dt.days
    insufficient_mask = base["history_days"] < min_history_days
    exclusions["insufficient_history"] = int(insufficient_mask.sum())
    base = base.loc[~insufficient_mask].copy()

    if base.empty:
        return pd.DataFrame(columns=empty_result_columns), exclusions

    label = pd.Series(0, index=base.index, dtype=int)
    if not all_outcomes.empty and not base.empty:
        merged_label = base[["patient_id", "prediction_anchor_date"]].merge(
            all_outcomes[["patient_id", "outcome_at"]], on="patient_id", how="left"
        )
        merged_label["days_to_outcome"] = (
            merged_label["outcome_at"] - merged_label["prediction_anchor_date"]
        ).dt.days
        positive = merged_label.groupby("patient_id")["days_to_outcome"].apply(
            lambda series: bool(((series > 0) & (series <= horizon_days)).any())
        )
        label = positive.reindex(base["patient_id"]).fillna(False).astype(int)
        label.index = base.index

    base["label"] = label

    return (
        base[
            [
                "patient_id",
                "label",
                "is_case",
                "prediction_anchor_date",
                "feature_cutoff",
                "history_days",
            ]
        ].reset_index(drop=True),
        exclusions,
    )
