from app.pipeline.splits import patient_level_split


def test_patient_level_split_is_disjoint_and_complete() -> None:
    patient_ids = [f"SYN-{index:04d}" for index in range(1, 41)]
    train_ids, test_ids = patient_level_split(
        patient_ids, test_size=0.25, random_state=42
    )

    assert set(train_ids).isdisjoint(test_ids)
    assert set(train_ids) | set(test_ids) == set(patient_ids)
    assert len(train_ids) + len(test_ids) == len(set(patient_ids))


def test_patient_level_split_is_stratified_when_feasible() -> None:
    patient_ids = [f"SYN-{index:04d}" for index in range(1, 41)]
    labels = {
        patient_id: 1 if index % 4 == 0 else 0
        for index, patient_id in enumerate(patient_ids, start=1)
    }

    train_ids, test_ids = patient_level_split(
        patient_ids, test_size=0.25, random_state=42, labels=labels
    )

    assert set(train_ids).isdisjoint(test_ids)
    assert set(train_ids) | set(test_ids) == set(patient_ids)

    train_positive_rate = sum(labels[pid] for pid in train_ids) / len(train_ids)
    test_positive_rate = sum(labels[pid] for pid in test_ids) / len(test_ids)
    overall_positive_rate = sum(labels.values()) / len(patient_ids)

    assert abs(train_positive_rate - overall_positive_rate) < 0.1
    assert abs(test_positive_rate - overall_positive_rate) < 0.1


def test_patient_level_split_falls_back_when_stratification_infeasible() -> None:
    patient_ids = [f"SYN-{index:04d}" for index in range(1, 11)]
    # A single positive example makes stratification infeasible; the split
    # must still succeed and remain disjoint/complete.
    labels = {
        patient_id: 1 if index == 1 else 0
        for index, patient_id in enumerate(patient_ids, start=1)
    }

    train_ids, test_ids = patient_level_split(
        patient_ids, test_size=0.3, random_state=42, labels=labels
    )

    assert set(train_ids).isdisjoint(test_ids)
    assert set(train_ids) | set(test_ids) == set(patient_ids)
