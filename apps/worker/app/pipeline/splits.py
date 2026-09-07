"""Patient-level splitting utilities that prevent cross-fold leakage."""

from __future__ import annotations

from collections.abc import Iterable

from sklearn.model_selection import train_test_split


def patient_level_split(
    patient_ids: Iterable[str],
    test_size: float,
    random_state: int,
) -> tuple[list[str], list[str]]:
    """Split unique patient IDs into disjoint train/test sets."""

    unique_ids = sorted(set(patient_ids))
    if len(unique_ids) <= 1:
        return unique_ids, []
    train_ids, test_ids = train_test_split(unique_ids, test_size=test_size, random_state=random_state)
    return sorted(train_ids), sorted(test_ids)
