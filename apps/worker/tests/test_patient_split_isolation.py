from app.pipeline.splits import patient_level_split


def test_patient_level_split_is_disjoint_and_complete() -> None:
    patient_ids = [f"SYN-{index:04d}" for index in range(1, 41)]
    train_ids, test_ids = patient_level_split(patient_ids, test_size=0.25, random_state=42)

    assert set(train_ids).isdisjoint(test_ids)
    assert set(train_ids) | set(test_ids) == set(patient_ids)
    assert len(train_ids) + len(test_ids) == len(set(patient_ids))
