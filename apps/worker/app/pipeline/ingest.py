"""Dataset ingestion helpers for inline and private-storage research payloads."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

import pandas as pd
from pydantic import BaseModel
from pydantic import ValidationError

from app.schemas import DatasetPayload

PARTICIPANT_COLUMNS = [
    "patient_id",
    "sex",
    "age",
    "diagnosis_date",
    "reference_date",
    "cohort_label",
]
OBSERVATION_COLUMNS = ["patient_id", "variable_code", "value", "observed_at", "unit"]
OUTCOME_COLUMNS = ["patient_id", "outcome_code", "outcome_at", "label"]
ENCOUNTER_COLUMNS = ["patient_id", "encountered_at", "encounter_type"]
DATA_DICTIONARY_COLUMNS = [
    "variable_code",
    "display_name",
    "unit",
    "domain",
    "is_treatment_related",
    "is_outcome_derived",
    "is_post_index_only",
]
TABLE_NAMES = (
    "participants",
    "observations",
    "outcomes",
    "encounters",
    "data_dictionary",
)
REQUIRED_SOURCE_COLUMNS = {
    "participants": {"patient_id"},
    "observations": {"patient_id", "variable_code", "value", "observed_at"},
    "outcomes": {"patient_id", "outcome_code", "outcome_at"},
    "encounters": {"patient_id", "encountered_at"},
    "data_dictionary": {"variable_code"},
}
MAX_ARCHIVE_MEMBERS = 16
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
DIRECT_IDENTIFIER_COLUMNS = {
    "address",
    "date_of_birth",
    "dob",
    "email",
    "first_name",
    "last_name",
    "medical_record_number",
    "name",
    "nhs_number",
    "phone",
    "postcode",
}
COLUMN_ALIASES = {
    "participants": {"sex_at_birth": "sex"},
    "outcomes": {
        "cancer_type": "outcome_code",
        "diagnosis_date": "outcome_at",
        "incident_flag": "label",
    },
    "encounters": {"encounter_at": "encountered_at"},
}


class DatasetIngestionError(ValueError):
    """Raised when an uploaded dataset cannot satisfy the research contract."""


def _normalise_column_name(column: object) -> str:
    return str(column).strip().lower().replace("-", "_").replace(" ", "_")


def _normalise_frame(table_name: str, frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [_normalise_column_name(column) for column in frame.columns]
    aliases = COLUMN_ALIASES.get(table_name, {})
    for source, target in aliases.items():
        if source in frame.columns and target not in frame.columns:
            frame = frame.rename(columns={source: target})
    return frame


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for row in (
        frame.astype(object).where(pd.notna(frame), None).to_dict(orient="records")
    ):
        records.append({key: value for key, value in row.items() if value is not None})
    return records


def _validate_source_frames(frames: dict[str, pd.DataFrame]) -> None:
    problems: list[str] = []
    missing_tables = sorted(set(TABLE_NAMES) - set(frames))
    if missing_tables:
        problems.append(f"Missing required tables: {', '.join(missing_tables)}.")

    for table_name, frame in frames.items():
        direct_identifiers = sorted(DIRECT_IDENTIFIER_COLUMNS & set(frame.columns))
        if direct_identifiers:
            problems.append(
                f"{table_name} contains direct identifier columns: {', '.join(direct_identifiers)}."
            )
        required_columns = REQUIRED_SOURCE_COLUMNS.get(table_name, set())
        missing_columns = sorted(required_columns - set(frame.columns))
        if missing_columns:
            problems.append(
                f"{table_name} missing required columns: {', '.join(missing_columns)}."
            )

    if problems:
        raise DatasetIngestionError(" ".join(problems))


def _read_table(data: bytes, suffix: str, table_name: str) -> pd.DataFrame:
    try:
        if suffix == ".csv":
            return _normalise_frame(table_name, pd.read_csv(BytesIO(data)))
        if suffix == ".parquet":
            return _normalise_frame(table_name, pd.read_parquet(BytesIO(data)))
        if suffix == ".json":
            payload = json.loads(data.decode("utf-8"))
            if isinstance(payload, dict) and table_name in payload:
                payload = payload[table_name]
            if not isinstance(payload, list):
                raise DatasetIngestionError(
                    f"{table_name}.json must contain an array of records."
                )
            return _normalise_frame(table_name, pd.DataFrame(payload))
    except (UnicodeDecodeError, ValueError, OSError) as exc:
        raise DatasetIngestionError(
            f"Unable to read {table_name}{suffix}: {exc}"
        ) from exc

    raise DatasetIngestionError(f"Unsupported table format {suffix} for {table_name}.")


def _load_zip_tables(data: bytes) -> dict[str, pd.DataFrame]:
    try:
        with ZipFile(BytesIO(data)) as archive:
            members = [member for member in archive.infolist() if not member.is_dir()]
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise DatasetIngestionError("Archive contains too many files.")
            if (
                sum(member.file_size for member in members)
                > MAX_ARCHIVE_UNCOMPRESSED_BYTES
            ):
                raise DatasetIngestionError(
                    "Archive exceeds the allowed uncompressed size."
                )

            frames: dict[str, pd.DataFrame] = {}
            for member in members:
                member_path = PurePosixPath(member.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise DatasetIngestionError("Archive contains an unsafe file path.")
                suffix = member_path.suffix.lower()
                table_name = _normalise_column_name(member_path.stem)
                if table_name not in TABLE_NAMES:
                    continue
                if table_name in frames:
                    raise DatasetIngestionError(
                        f"Archive contains more than one {table_name} table."
                    )
                frames[table_name] = _read_table(
                    archive.read(member), suffix, table_name
                )
            return frames
    except BadZipFile as exc:
        raise DatasetIngestionError("Uploaded ZIP archive is invalid.") from exc


def _load_normalised_table(data: bytes, suffix: str) -> dict[str, pd.DataFrame]:
    normalised = _read_table(data, suffix, "normalised")
    if "table" not in normalised.columns:
        raise DatasetIngestionError(
            "A single CSV or Parquet upload must include a 'table' column naming each contract table."
        )

    frames: dict[str, pd.DataFrame] = {}
    for table_name, group in normalised.groupby("table", dropna=False):
        canonical_name = _normalise_column_name(table_name)
        if canonical_name not in TABLE_NAMES:
            raise DatasetIngestionError(
                f"Unsupported table value '{table_name}' in normalized upload."
            )
        if canonical_name in frames:
            raise DatasetIngestionError(
                f"Normalized upload contains repeated table group {canonical_name}."
            )
        frames[canonical_name] = _normalise_frame(
            canonical_name, group.drop(columns=["table"]).reset_index(drop=True)
        )
    return frames


def dataset_from_bytes(data: bytes, filename: str) -> DatasetPayload:
    """Parse a supported upload into the typed ORAMA research dataset contract."""

    suffix = PurePosixPath(filename).suffix.lower()
    if suffix == ".zip":
        frames = _load_zip_tables(data)
    elif suffix in {".csv", ".parquet"}:
        frames = _load_normalised_table(data, suffix)
    else:
        raise DatasetIngestionError("Only CSV, Parquet, and ZIP uploads are supported.")

    _validate_source_frames(frames)
    try:
        return DatasetPayload.model_validate(
            {table_name: _records(frames[table_name]) for table_name in TABLE_NAMES}
        )
    except ValidationError as exc:
        raise DatasetIngestionError(
            f"Dataset values do not satisfy the contract: {exc}"
        ) from exc


def dataset_from_storage(
    object_key: str, data: bytes, filename: str | None = None
) -> DatasetPayload:
    """Parse a private object using its object key solely to determine the file format."""

    return dataset_from_bytes(data, filename or PurePosixPath(object_key).name)


def _frame_from_models(items: list[BaseModel], columns: list[str]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [item.model_dump(mode="json") for item in items], columns=columns
    )


def dataset_to_frames(dataset: DatasetPayload) -> dict[str, pd.DataFrame]:
    """Convert a typed dataset payload into pandas DataFrames."""

    return {
        "participants": _frame_from_models(dataset.participants, PARTICIPANT_COLUMNS),
        "observations": _frame_from_models(dataset.observations, OBSERVATION_COLUMNS),
        "outcomes": _frame_from_models(dataset.outcomes, OUTCOME_COLUMNS),
        "encounters": _frame_from_models(dataset.encounters, ENCOUNTER_COLUMNS),
        "data_dictionary": _frame_from_models(
            dataset.data_dictionary, DATA_DICTIONARY_COLUMNS
        ),
    }
