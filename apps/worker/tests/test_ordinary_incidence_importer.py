import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

from app.importers import ordinary_incidence
from app.importers.ordinary_incidence import (
    OrdinaryIncidenceImportError,
    pack_ordinary_incidence,
)
from app.pipeline.ingest import dataset_from_bytes, dataset_to_frames
from app.pipeline.validation import validate_frames


def _write_source_bundle(
    tmp_path: Path,
    *,
    simulation_only: bool = True,
    status: str = "completed",
) -> Path:
    source = tmp_path / "ordinary-incidence"
    canonical = source / "canonical"
    canonical.mkdir(parents=True)
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "ordinary-incidence-test",
                "cohort_class": "ordinary_incidence",
                "simulation_only": simulation_only,
                "status": status,
                "canonical_status": "created",
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {"patient_id": "SYN-1", "sex": "F", "birth_date": "1970-01-01"},
            {"patient_id": "SYN-2", "sex": "M", "birth_date": "1972-01-01"},
            {"patient_id": "SYN-3", "sex": "X", "birth_date": "1974-01-01"},
        ]
    ).to_parquet(canonical / "patients.parquet", index=False)
    pd.DataFrame(
        [
            {
                "patient_id": "SYN-1",
                "event_date": "2024-01-01T00:00:00Z",
                "encounter_type": "outpatient",
                "feature_name": "glucose",
                "value": 4.6,
                "unit": "mg/dL",
                "is_missing": False,
                "provenance": "synthea_native",
                "augmentation_module": None,
            },
            {
                "patient_id": "SYN-1",
                "event_date": "2025-01-01T00:00:00Z",
                "encounter_type": "lab",
                "feature_name": "ca_19_9",
                "value": 24.0,
                "unit": "U/mL",
                "is_missing": False,
                "provenance": "augmented",
                "augmentation_module": "ca19_9",
            },
            {
                "patient_id": "SYN-2",
                "event_date": "2024-04-01T00:00:00Z",
                "encounter_type": "outpatient",
                "feature_name": "glucose",
                "value": 5.2,
                "unit": "mg/dL",
                "is_missing": False,
                "provenance": "synthea_native",
                "augmentation_module": None,
            },
            {
                "patient_id": "SYN-2",
                "event_date": "2024-12-01T00:00:00Z",
                "encounter_type": "outpatient",
                "feature_name": "weight",
                "value": 75.0,
                "unit": "kg",
                "is_missing": False,
                "provenance": "synthea_native",
                "augmentation_module": None,
            },
            {
                "patient_id": "SYN-3",
                "event_date": "2024-06-01T00:00:00Z",
                "encounter_type": "lab",
                "feature_name": "insulin",
                "value": 8.0,
                "unit": "uIU/mL",
                "is_missing": False,
                "provenance": "augmented",
                "augmentation_module": "insulin",
            },
        ]
    ).to_parquet(canonical / "events.parquet", index=False)
    pd.DataFrame(
        [{"patient_id": "SYN-1", "condition_code": "example-condition"}]
    ).to_parquet(canonical / "conditions.parquet", index=False)
    pd.DataFrame(
        [
            {
                "patient_id": "SYN-1",
                "outcome_type": "cancer",
                "outcome_date": "2025-06-01T00:00:00Z",
            },
            {
                "patient_id": "SYN-1",
                "outcome_type": "diabetes",
                "outcome_date": "2025-05-01T00:00:00Z",
            },
            {
                "patient_id": "SYN-2",
                "outcome_type": "diabetes",
                "outcome_date": "2025-07-01T00:00:00Z",
            },
        ]
    ).to_parquet(canonical / "outcomes.parquet", index=False)
    return source


def test_packer_creates_parser_valid_endpoint_specific_archive(tmp_path: Path) -> None:
    source = _write_source_bundle(tmp_path)
    output = tmp_path / "cancer-upload.zip"

    result = pack_ordinary_incidence(source, output, "cancer")

    assert result.output_path == output
    assert result.participants == 2
    assert result.observations == 3
    assert result.outcomes == 1
    assert result.encounters == 3
    assert result.data_dictionary_entries == 2
    assert result.excluded_augmented_events == 2
    assert result.excluded_patients_without_safe_events == 1
    with ZipFile(output) as archive:
        assert set(archive.namelist()) == {
            "participants.parquet",
            "observations.parquet",
            "outcomes.parquet",
            "encounters.parquet",
            "data_dictionary.parquet",
            "orama_import_manifest.json",
        }
        import_manifest = json.loads(archive.read("orama_import_manifest.json"))
    assert import_manifest["endpoint"] == "cancer"
    assert import_manifest["reference_date_policy"] == "latest_safe_native_event"

    dataset = dataset_from_bytes(output.read_bytes(), output.name)
    frames = dataset_to_frames(dataset)
    validate_frames(frames)
    assert set(frames["participants"]["patient_id"]) == {"SYN-1", "SYN-2"}
    assert "birth_date" not in frames["participants"].columns
    assert frames["participants"].set_index("patient_id").loc["SYN-2", "age"] == 52.9
    assert set(frames["observations"]["variable_code"]) == {"glucose", "weight"}
    assert set(frames["outcomes"]["outcome_code"]) == {"cancer"}
    control = frames["participants"].set_index("patient_id").loc["SYN-2"]
    assert control["reference_date"] == "2024-12-01T00:00:00Z"


def test_packer_rejects_non_synthetic_or_incomplete_source(tmp_path: Path) -> None:
    non_synthetic = _write_source_bundle(
        tmp_path / "non-synthetic", simulation_only=False
    )
    with pytest.raises(OrdinaryIncidenceImportError, match="simulation_only"):
        pack_ordinary_incidence(non_synthetic, tmp_path / "non-synthetic.zip", "cancer")

    incomplete = _write_source_bundle(tmp_path / "incomplete", status="running")
    with pytest.raises(OrdinaryIncidenceImportError, match="status=completed"):
        pack_ordinary_incidence(incomplete, tmp_path / "incomplete.zip", "cancer")


def test_packer_rejects_archive_over_the_worker_member_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _write_source_bundle(tmp_path)
    output = tmp_path / "too-large.zip"
    monkeypatch.setattr(ordinary_incidence, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 1)

    with pytest.raises(OrdinaryIncidenceImportError, match="128 MiB"):
        pack_ordinary_incidence(source, output, "cancer")

    assert not output.exists()
