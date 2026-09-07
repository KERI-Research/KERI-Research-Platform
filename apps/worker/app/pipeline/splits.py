"""Patient-level splitting utilities that prevent cross-fold leakage."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from sklearn.model_selection import train_test_split


def _can_stratify(unique_ids: list[str], labels: Mapping[str, int], test_size: float) -> bool:
    """Return whether a stratified split is feasible for these labels.

    Stratification requires at least two classes, each with enough members
    that both the train and test folds can receive at least one example of
    every class.
    """

    values = [labels[patient_id] for patient_id in unique_ids if patient_id in labels]
    if len(values) != len(unique_ids):
        return False
    class_counts: dict[int, int] = {}
    for value in values:
        class_counts[value] = class_counts.get(value, 0) + 1
    if len(class_counts) < 2:
        return False
    n_test = max(1, round(len(unique_ids) * test_size))
    n_train = len(unique_ids) - n_test
    if n_test < len(class_counts) or n_train < len(class_counts):
        return False
    return all(count >= 2 for count in class_counts.values())


def patient_level_split(
    patient_ids: Iterable[str],
    test_size: float,
    random_state: int,
    labels: Mapping[str, int] | None = None,
) -> tuple[list[str], list[str]]:
    """Split unique patient IDs into disjoint train/test sets.

    When ``labels`` is provided and stratification is feasible (at least two
    classes with enough members to appear in both folds), the split is
    stratified by label so both train and test folds retain a similar class
    balance. Otherwise falls back to a plain random split. In all cases, a
    given patient_id appears in exactly one of the two returned sets.
    """

    unique_ids = sorted(set(patient_ids))
    if len(unique_ids) <= 1:
        return unique_ids, []

    stratify = None
    if labels is not None and _can_stratify(unique_ids, labels, test_size):
        stratify = [labels[patient_id] for patient_id in unique_ids]

    train_ids, test_ids = train_test_split(
        unique_ids,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify,
    )
    return sorted(train_ids), sorted(test_ids)
