import pandas as pd
import pytest

from app.pipeline.validation import SchemaValidationError, validate_frames


@pytest.mark.parametrize(
    ("frames", "expected_substring"),
    [
        (
            {
                "participants": pd.DataFrame([{"patient_id": "SYN-0001"}]),
                "observations": pd.DataFrame(
                    [
                        {
                            "patient_id": "SYN-0001",
                            "value": 1.0,
                            "observed_at": "2026-01-01",
                        }
                    ]
                ),
                "outcomes": pd.DataFrame(
                    [
                        {
                            "patient_id": "SYN-0001",
                            "outcome_code": "x",
                            "outcome_at": "2026-02-01",
                        }
                    ]
                ),
                "encounters": pd.DataFrame(
                    [{"patient_id": "SYN-0001", "encountered_at": "2025-01-01"}]
                ),
                "data_dictionary": pd.DataFrame([{"variable_code": "lab_a"}]),
            },
            "observations missing required columns: variable_code",
        ),
        (
            {
                "participants": pd.DataFrame([{"patient_id": "SYN-0001"}]),
                "observations": pd.DataFrame(
                    [
                        {
                            "patient_id": "SYN-0001",
                            "variable_code": "lab_a",
                            "value": 1.0,
                            "observed_at": "not-a-date",
                        }
                    ]
                ),
                "outcomes": pd.DataFrame(
                    [
                        {
                            "patient_id": "SYN-0001",
                            "outcome_code": "x",
                            "outcome_at": "2026-02-01",
                        }
                    ]
                ),
                "encounters": pd.DataFrame(
                    [{"patient_id": "SYN-0001", "encountered_at": "2025-01-01"}]
                ),
                "data_dictionary": pd.DataFrame([{"variable_code": "lab_a"}]),
            },
            "observations.observed_at contains invalid timestamps",
        ),
        (
            {
                "participants": pd.DataFrame([{"patient_id": "SYN-0001"}]),
                "observations": pd.DataFrame(
                    [
                        {
                            "patient_id": "SYN-0001",
                            "variable_code": "drug_after_index",
                            "value": 1.0,
                            "observed_at": "2026-01-01",
                        }
                    ]
                ),
                "outcomes": pd.DataFrame(
                    [
                        {
                            "patient_id": "SYN-0001",
                            "outcome_code": "x",
                            "outcome_at": "2026-02-01",
                        }
                    ]
                ),
                "encounters": pd.DataFrame(
                    [{"patient_id": "SYN-0001", "encountered_at": "2025-01-01"}]
                ),
                "data_dictionary": pd.DataFrame(
                    [
                        {
                            "variable_code": "drug_after_index",
                            "is_treatment_related": True,
                            "is_outcome_derived": False,
                            "is_post_index_only": False,
                        }
                    ]
                ),
            },
            "observations include forbidden variable codes",
        ),
        (
            {
                "participants": pd.DataFrame([{"patient_id": "SYN-0001"}]),
                "observations": pd.DataFrame(
                    [
                        {
                            "patient_id": "SYN-UNKNOWN",
                            "variable_code": "lab_a",
                            "value": 1.0,
                            "observed_at": "2026-01-01",
                            "unit": "u/L",
                        }
                    ]
                ),
                "outcomes": pd.DataFrame(
                    [
                        {
                            "patient_id": "SYN-0001",
                            "outcome_code": "x",
                            "outcome_at": "2026-02-01",
                        }
                    ]
                ),
                "encounters": pd.DataFrame(
                    [{"patient_id": "SYN-0001", "encountered_at": "2025-01-01"}]
                ),
                "data_dictionary": pd.DataFrame(
                    [{"variable_code": "lab_a", "unit": "u/L"}]
                ),
            },
            "observations contains 1 records for unknown participants",
        ),
        (
            {
                "participants": pd.DataFrame([{"patient_id": "SYN-0001"}]),
                "observations": pd.DataFrame(
                    [
                        {
                            "patient_id": "SYN-0001",
                            "variable_code": "lab_a",
                            "value": 1.0,
                            "observed_at": "2026-01-01",
                            "unit": "mmol/L",
                        }
                    ]
                ),
                "outcomes": pd.DataFrame(
                    [
                        {
                            "patient_id": "SYN-0001",
                            "outcome_code": "x",
                            "outcome_at": "2026-02-01",
                        }
                    ]
                ),
                "encounters": pd.DataFrame(
                    [{"patient_id": "SYN-0001", "encountered_at": "2025-01-01"}]
                ),
                "data_dictionary": pd.DataFrame(
                    [{"variable_code": "lab_a", "unit": "g/L"}]
                ),
            },
            "observations contain units that do not match",
        ),
        (
            {
                "participants": pd.DataFrame(
                    [{"patient_id": "researcher@example.org"}]
                ),
                "observations": pd.DataFrame(
                    [
                        {
                            "patient_id": "researcher@example.org",
                            "variable_code": "lab_a",
                            "value": 1.0,
                            "observed_at": "2026-01-01",
                            "unit": "u/L",
                        }
                    ]
                ),
                "outcomes": pd.DataFrame(
                    [
                        {
                            "patient_id": "researcher@example.org",
                            "outcome_code": "x",
                            "outcome_at": "2026-02-01",
                        }
                    ]
                ),
                "encounters": pd.DataFrame(
                    [
                        {
                            "patient_id": "researcher@example.org",
                            "encountered_at": "2025-01-01",
                        }
                    ]
                ),
                "data_dictionary": pd.DataFrame(
                    [{"variable_code": "lab_a", "unit": "u/L"}]
                ),
            },
            "participants.patient_id appears to contain a direct identifier",
        ),
    ],
)
def test_schema_validation_rejects_invalid_inputs(
    frames: dict[str, pd.DataFrame], expected_substring: str
) -> None:
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_frames(frames)
    assert expected_substring in str(exc_info.value)
