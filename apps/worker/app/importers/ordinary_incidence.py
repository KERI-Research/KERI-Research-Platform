"""Package approved ordinary-incidence source bundles for ORAMA upload."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import mkstemp
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import pandas as pd

from app.pipeline.ingest import (
    MAX_ARCHIVE_MEMBERS,
    MAX_ARCHIVE_UNCOMPRESSED_BYTES,
    TABLE_NAMES,
    dataset_from_bytes,
    dataset_to_frames,
)
from app.pipeline.validation import validate_frames

SOURCE_TABLES = ("patients", "events", "conditions", "outcomes")
REQUIRED_EVENT_COLUMNS = {
    "patient_id",
    "event_date",
    "encounter_type",
    "feature_name",
    "value",
    "unit",
    "is_missing",
    "provenance",
    "augmentation_module",
}
REQUIRED_OUTCOME_COLUMNS = {"patient_id", "outcome_type", "outcome_date"}
NATIVE_PROVENANCE = "synthea_native"
CONTROL_REFERENCE_POLICY = "latest_safe_native_event"


class OrdinaryIncidenceImportError(ValueError):
    """Raised when an ordinary-incidence bundle is unsafe or incomplete."""


@dataclass(frozen=True)
class OrdinaryIncidencePackResult:
    """Summary of one validated ORAMA upload package."""

    output_path: Path
    endpoint: str
    participants: int
    observations: int
    outcomes: int
    encounters: int
    data_dictionary_entries: int
    excluded_augmented_events: int
    excluded_patients_without_safe_events: int
    archive_bytes: int
    archive_member_bytes: int


def _load_manifest(source_directory: Path) -> dict[str, object]:
    manifest_path = source_directory / "manifest.json"
    if not manifest_path.is_file():
        raise OrdinaryIncidenceImportError("Source bundle is missing manifest.json.")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OrdinaryIncidenceImportError(
            "Source manifest.json is invalid JSON."
        ) from exc

    if not isinstance(manifest, dict):
        raise OrdinaryIncidenceImportError(
            "Source manifest.json must contain an object."
        )
    if manifest.get("simulation_only") is not True:
        raise OrdinaryIncidenceImportError(
            "Only source bundles explicitly marked simulation_only=true may be packaged."
        )
    if manifest.get("status") != "completed":
        raise OrdinaryIncidenceImportError(
            "Source bundle must have manifest status=completed before packaging."
        )
    if manifest.get("canonical_status") != "created":
        raise OrdinaryIncidenceImportError(
            "Source bundle must have canonical_status=created before packaging."
        )
    if not isinstance(manifest.get("run_id"), str) or not manifest["run_id"].strip():
        raise OrdinaryIncidenceImportError(
            "Source manifest must contain a non-empty run_id."
        )
    return manifest


def _load_source_tables(source_directory: Path) -> dict[str, pd.DataFrame]:
    canonical_directory = source_directory / "canonical"
    tables: dict[str, pd.DataFrame] = {}
    for table_name in SOURCE_TABLES:
        table_path = canonical_directory / f"{table_name}.parquet"
        if not table_path.is_file():
            raise OrdinaryIncidenceImportError(
                f"Source bundle is missing canonical/{table_name}.parquet."
            )
        tables[table_name] = pd.read_parquet(table_path)

    missing_event_columns = sorted(
        REQUIRED_EVENT_COLUMNS - set(tables["events"].columns)
    )
    if missing_event_columns:
        raise OrdinaryIncidenceImportError(
            "Source events table is missing required columns: "
            f"{', '.join(missing_event_columns)}."
        )
    missing_outcome_columns = sorted(
        REQUIRED_OUTCOME_COLUMNS - set(tables["outcomes"].columns)
    )
    if missing_outcome_columns:
        raise OrdinaryIncidenceImportError(
            "Source outcomes table is missing required columns: "
            f"{', '.join(missing_outcome_columns)}."
        )
    if "patient_id" not in tables["patients"].columns:
        raise OrdinaryIncidenceImportError(
            "Source patients table is missing required column patient_id."
        )
    return tables


def _normalised_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def _false_values(series: pd.Series) -> pd.Series:
    return series.map(
        lambda value: (
            value is False
            or (
                isinstance(value, str) and value.strip().lower() in {"false", "0", "no"}
            )
        )
    )


def _safe_observations(events: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    frame = events.copy()
    frame["patient_id"] = _normalised_text(frame["patient_id"])
    frame["variable_code"] = _normalised_text(frame["feature_name"])
    frame["observed_at"] = pd.to_datetime(
        frame["event_date"], errors="coerce", utc=True
    )
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame["unit"] = frame["unit"].where(frame["unit"].notna(), None)

    is_native = _normalised_text(frame["provenance"]).str.lower().eq(NATIVE_PROVENANCE)
    is_unaugmented = frame["augmentation_module"].isna() | _normalised_text(
        frame["augmentation_module"]
    ).eq("")
    augmented_events = ~(is_native & is_unaugmented)
    valid_rows = (
        is_native
        & is_unaugmented
        & _false_values(frame["is_missing"])
        & frame["patient_id"].notna()
        & frame["patient_id"].ne("")
        & frame["variable_code"].notna()
        & frame["variable_code"].ne("")
        & frame["observed_at"].notna()
        & frame["value"].notna()
        & np.isfinite(frame["value"])
    )
    observations = frame.loc[
        valid_rows,
        [
            "patient_id",
            "variable_code",
            "value",
            "observed_at",
            "unit",
            "encounter_type",
        ],
    ].copy()
    if observations.empty:
        raise OrdinaryIncidenceImportError(
            "Source bundle has no safe native observations after provenance and value checks."
        )
    return observations, int(augmented_events.sum())


def _build_participants(
    patients: pd.DataFrame, observations: pd.DataFrame
) -> tuple[pd.DataFrame, int]:
    participant_frame = patients.copy()
    participant_frame["patient_id"] = _normalised_text(participant_frame["patient_id"])
    if (
        participant_frame["patient_id"].isna().any()
        or participant_frame["patient_id"].eq("").any()
    ):
        raise OrdinaryIncidenceImportError(
            "Source patients table contains blank patient_id values."
        )
    if participant_frame["patient_id"].duplicated().any():
        raise OrdinaryIncidenceImportError(
            "Source patients table contains duplicate patient_id values."
        )

    if "birth_date" in participant_frame.columns:
        participant_frame["birth_date"] = pd.to_datetime(
            participant_frame["birth_date"], errors="coerce", utc=True
        )
    follow_up = observations.groupby("patient_id", as_index=False).agg(
        reference_date=("observed_at", "max")
    )
    participant_columns = ["patient_id"]
    if "sex" in participant_frame.columns:
        participant_columns.append("sex")
    if "birth_date" in participant_frame.columns:
        participant_columns.append("birth_date")
    participants = participant_frame[participant_columns].merge(
        follow_up, on="patient_id", how="inner"
    )
    if "birth_date" in participants.columns:
        age_years = (
            participants["reference_date"] - participants["birth_date"]
        ).dt.total_seconds() / (365.25 * 24 * 60 * 60)
        participants["age"] = age_years.where(age_years.ge(0)).round(1)
        participants = participants.drop(columns="birth_date")
    excluded_patients = len(participant_frame) - len(participants)
    if participants.empty:
        raise OrdinaryIncidenceImportError(
            "No source participants have a safe native observation for follow-up anchoring."
        )
    return participants, excluded_patients


def _build_outcomes(
    outcomes: pd.DataFrame, participant_ids: pd.Series, endpoint: str
) -> pd.DataFrame:
    frame = outcomes.copy()
    frame["patient_id"] = _normalised_text(frame["patient_id"])
    frame["outcome_type"] = _normalised_text(frame["outcome_type"]).str.lower()
    frame["outcome_at"] = pd.to_datetime(
        frame["outcome_date"], errors="coerce", utc=True
    )

    available_endpoints = sorted(
        value for value in frame["outcome_type"].dropna().unique().tolist() if value
    )
    if endpoint not in available_endpoints:
        raise OrdinaryIncidenceImportError(
            f"Endpoint '{endpoint}' is unavailable. Available endpoints: {', '.join(available_endpoints)}."
        )

    selected = frame.loc[
        frame["outcome_type"].eq(endpoint)
        & frame["outcome_at"].notna()
        & frame["patient_id"].isin(set(participant_ids)),
        ["patient_id", "outcome_at"],
    ].copy()
    selected = selected.sort_values("outcome_at").drop_duplicates("patient_id")
    selected["outcome_code"] = endpoint
    selected["label"] = 1
    return selected[["patient_id", "outcome_code", "outcome_at", "label"]]


def _build_data_dictionary(observations: pd.DataFrame) -> pd.DataFrame:
    unit_counts = (
        observations.assign(
            _unit_key=observations["unit"]
            .fillna("<missing>")
            .astype(str)
            .str.strip()
            .str.lower()
        )
        .groupby("variable_code")["_unit_key"]
        .nunique()
    )
    inconsistent_units = sorted(unit_counts[unit_counts > 1].index.tolist())
    if inconsistent_units:
        raise OrdinaryIncidenceImportError(
            "Safe native observations contain inconsistent units for: "
            f"{', '.join(inconsistent_units)}."
        )

    dictionary = (
        observations[["variable_code", "unit"]]
        .drop_duplicates("variable_code")
        .sort_values("variable_code")
        .reset_index(drop=True)
    )
    dictionary["display_name"] = dictionary["variable_code"]
    dictionary["domain"] = "ordinary_incidence"
    dictionary["is_treatment_related"] = False
    dictionary["is_outcome_derived"] = False
    dictionary["is_post_index_only"] = False
    return dictionary[
        [
            "variable_code",
            "display_name",
            "unit",
            "domain",
            "is_treatment_related",
            "is_outcome_derived",
            "is_post_index_only",
        ]
    ]


def _parquet_bytes(frame: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    frame.to_parquet(buffer, index=False)
    return buffer.getvalue()


def _build_archive(
    frames: dict[str, pd.DataFrame], import_manifest: dict[str, object]
) -> tuple[bytes, int]:
    members = {
        f"{table_name}.parquet": _parquet_bytes(frames[table_name])
        for table_name in TABLE_NAMES
    }
    members["orama_import_manifest.json"] = json.dumps(
        import_manifest, indent=2, sort_keys=True
    ).encode("utf-8")
    member_bytes = sum(len(data) for data in members.values())
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise OrdinaryIncidenceImportError(
            "Generated archive contains too many members."
        )
    if member_bytes > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise OrdinaryIncidenceImportError(
            "Generated archive exceeds ORAMA's 128 MiB uncompressed member limit."
        )

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for filename, data in members.items():
            archive.writestr(filename, data)
    return buffer.getvalue(), member_bytes


def _write_archive(output_path: Path, archive: bytes, overwrite: bool) -> None:
    if output_path.exists() and not overwrite:
        raise OrdinaryIncidenceImportError(
            f"Output path already exists: {output_path}. Use --overwrite to replace it."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = mkstemp(
        prefix=f".{output_path.stem}-", suffix=".tmp", dir=output_path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(archive)
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def pack_ordinary_incidence(
    source_directory: Path | str,
    output_path: Path | str,
    endpoint: str,
    *,
    overwrite: bool = False,
) -> OrdinaryIncidencePackResult:
    """Create a validated endpoint-specific ORAMA ZIP from canonical source data."""

    source_path = Path(source_directory)
    destination = Path(output_path)
    normalized_endpoint = endpoint.strip().lower()
    if not source_path.is_dir():
        raise OrdinaryIncidenceImportError(
            f"Source directory does not exist: {source_path}."
        )
    if destination.suffix.lower() != ".zip":
        raise OrdinaryIncidenceImportError("Output path must use the .zip extension.")
    if not normalized_endpoint:
        raise OrdinaryIncidenceImportError("An endpoint must be selected.")

    source_manifest = _load_manifest(source_path)
    source_tables = _load_source_tables(source_path)
    observations, excluded_augmented_events = _safe_observations(
        source_tables["events"]
    )
    participants, excluded_patients = _build_participants(
        source_tables["patients"], observations
    )
    participant_ids = participants["patient_id"]
    observations = observations.loc[
        observations["patient_id"].isin(set(participant_ids))
    ].copy()
    outcomes = _build_outcomes(
        source_tables["outcomes"], participant_ids, normalized_endpoint
    )
    encounters = (
        observations[["patient_id", "observed_at", "encounter_type"]]
        .rename(columns={"observed_at": "encountered_at"})
        .drop_duplicates()
        .reset_index(drop=True)
    )
    observations = observations[
        ["patient_id", "variable_code", "value", "observed_at", "unit"]
    ].reset_index(drop=True)
    data_dictionary = _build_data_dictionary(observations)
    frames = {
        "participants": participants.reset_index(drop=True),
        "observations": observations,
        "outcomes": outcomes.reset_index(drop=True),
        "encounters": encounters,
        "data_dictionary": data_dictionary,
    }

    import_manifest = {
        "format_version": "1.0.0",
        "source_run_id": source_manifest["run_id"],
        "source_cohort_class": source_manifest.get("cohort_class"),
        "source_simulation_only": True,
        "endpoint": normalized_endpoint,
        "reference_date_policy": CONTROL_REFERENCE_POLICY,
        "included_event_provenance": NATIVE_PROVENANCE,
        "excluded_augmented_events": excluded_augmented_events,
        "excluded_patients_without_safe_events": excluded_patients,
        "unsupported_source_tables": ["conditions"],
    }
    archive, archive_member_bytes = _build_archive(frames, import_manifest)

    try:
        parsed_dataset = dataset_from_bytes(archive, destination.name)
        validate_frames(dataset_to_frames(parsed_dataset))
    except ValueError as exc:
        raise OrdinaryIncidenceImportError(
            f"Generated archive does not satisfy the ORAMA upload contract: {exc}"
        ) from exc

    _write_archive(destination, archive, overwrite)
    return OrdinaryIncidencePackResult(
        output_path=destination,
        endpoint=normalized_endpoint,
        participants=len(frames["participants"]),
        observations=len(frames["observations"]),
        outcomes=len(frames["outcomes"]),
        encounters=len(frames["encounters"]),
        data_dictionary_entries=len(frames["data_dictionary"]),
        excluded_augmented_events=excluded_augmented_events,
        excluded_patients_without_safe_events=excluded_patients,
        archive_bytes=len(archive),
        archive_member_bytes=archive_member_bytes,
    )


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Package a completed synthetic ordinary-incidence bundle for ORAMA."
    )
    parser.add_argument("source_directory", type=Path)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    """Run the ordinary-incidence upload packer from the command line."""

    arguments = _argument_parser().parse_args()
    try:
        result = pack_ordinary_incidence(
            arguments.source_directory,
            arguments.output,
            arguments.endpoint,
            overwrite=arguments.overwrite,
        )
    except OrdinaryIncidenceImportError as exc:
        raise SystemExit(f"Packaging failed: {exc}") from exc

    print(
        "Created validated ORAMA package "
        f"{result.output_path} for endpoint={result.endpoint}: "
        f"participants={result.participants}, observations={result.observations}, "
        f"outcomes={result.outcomes}, archive_bytes={result.archive_bytes}."
    )


if __name__ == "__main__":
    main()
