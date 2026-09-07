"""Synthetic dataset generation for tests and local demos."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from app.schemas import (
    DataDictionaryEntry,
    DatasetPayload,
    Encounter,
    Observation,
    Outcome,
    Participant,
)


def generate_synthetic_dataset(n_patients: int = 200, seed: int = 42) -> DatasetPayload:
    """Generate a clearly synthetic longitudinal dataset for research-only scaffolding."""

    rng = np.random.default_rng(seed)
    base_date = datetime(2026, 1, 1, tzinfo=timezone.utc)

    participants: list[Participant] = []
    observations: list[Observation] = []
    outcomes: list[Outcome] = []
    encounters: list[Encounter] = []
    data_dictionary = [
        DataDictionaryEntry(variable_code="lab_a", display_name="Synthetic Lab A", unit="u/L"),
        DataDictionaryEntry(variable_code="lab_b", display_name="Synthetic Lab B", unit="mg/dL"),
        DataDictionaryEntry(variable_code="symptom_score", display_name="Synthetic Symptom Score", unit="points"),
    ]

    for idx in range(1, n_patients + 1):
        patient_id = f"SYN-{idx:04d}"
        age = float(rng.integers(35, 81))
        sex = str(rng.choice(["F", "M", "X"]))
        reference_date = base_date + timedelta(days=int(rng.integers(0, 60)))
        cohort_label = "case" if idx % 4 == 0 else "control"
        participants.append(
            Participant(
                patient_id=patient_id,
                age=age,
                sex=sex,
                reference_date=reference_date,
                cohort_label=cohort_label,
            )
        )

        first_history = reference_date - timedelta(days=730)
        encounter_count = int(rng.integers(3, 8))
        for enc_idx in range(encounter_count):
            encounter_time = first_history + timedelta(days=enc_idx * 90 + int(rng.integers(0, 10)))
            encounters.append(
                Encounter(
                    patient_id=patient_id,
                    encountered_at=encounter_time,
                    encounter_type=str(rng.choice(["outpatient", "telehealth", "lab"])),
                )
            )

        baseline_a = rng.normal(10, 2)
        baseline_b = rng.normal(50, 8)
        symptom = rng.normal(2, 1)
        for step in range(6):
            observed_at = first_history + timedelta(days=step * 110 + int(rng.integers(0, 20)))
            drift = 0.25 * step if cohort_label == "case" else 0.05 * step
            observations.extend(
                [
                    Observation(
                        patient_id=patient_id,
                        variable_code="lab_a",
                        value=float(baseline_a + drift + rng.normal(0, 0.5)),
                        observed_at=observed_at,
                        unit="u/L",
                    ),
                    Observation(
                        patient_id=patient_id,
                        variable_code="lab_b",
                        value=float(baseline_b + drift * 3 + rng.normal(0, 1.0)),
                        observed_at=observed_at,
                        unit="mg/dL",
                    ),
                    Observation(
                        patient_id=patient_id,
                        variable_code="symptom_score",
                        value=float(symptom + drift * 0.5 + rng.normal(0, 0.3)),
                        observed_at=observed_at,
                        unit="points",
                    ),
                ]
            )

        if cohort_label == "case":
            outcomes.append(
                Outcome(
                    patient_id=patient_id,
                    outcome_code="synthetic_cancer_risk_signal",
                    outcome_at=reference_date + timedelta(days=int(rng.integers(30, 365))),
                    label=1,
                )
            )

    return DatasetPayload(
        participants=participants,
        observations=observations,
        outcomes=outcomes,
        encounters=encounters,
        data_dictionary=data_dictionary,
    )
