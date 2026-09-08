from io import BytesIO
from zipfile import ZipFile

import pytest

from app.pipeline.ingest import DatasetIngestionError, dataset_from_bytes


def _dataset_archive(*, participant_columns: str = "patient_id,sex,age") -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("participants.csv", f"{participant_columns}\nSYN-1,F,60\n")
        archive.writestr(
            "observations.csv",
            "patient_id,variable_code,value,observed_at,unit\nSYN-1,haemoglobin,128,2024-01-01T00:00:00Z,g/L\n",
        )
        archive.writestr(
            "outcomes.csv",
            "patient_id,cancer_type,diagnosis_date,incident_flag\nSYN-1,pan_cancer_incident,2025-01-01T00:00:00Z,1\n",
        )
        archive.writestr(
            "encounters.csv",
            "patient_id,encounter_at,encounter_type\nSYN-1,2024-01-02T00:00:00Z,consultation\n",
        )
        archive.writestr(
            "data_dictionary.json",
            '[{"variable_code":"haemoglobin","unit":"g/L"}]',
        )
    return buffer.getvalue()


def test_zip_dataset_is_parsed_into_the_worker_contract() -> None:
    dataset = dataset_from_bytes(_dataset_archive(), "synthetic_bundle.zip")

    assert dataset.participants[0].patient_id == "SYN-1"
    assert dataset.outcomes[0].outcome_code == "pan_cancer_incident"
    assert dataset.outcomes[0].label == 1
    assert (
        dataset.encounters[0].encountered_at.isoformat() == "2024-01-02T00:00:00+00:00"
    )


def test_zip_dataset_rejects_direct_identifier_columns() -> None:
    with pytest.raises(DatasetIngestionError, match="direct identifier"):
        dataset_from_bytes(
            _dataset_archive(participant_columns="patient_id,email"),
            "unsafe_bundle.zip",
        )
