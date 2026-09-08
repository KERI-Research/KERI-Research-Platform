"""Cloudflare R2 / S3-compatible object storage client for the ORAMA worker."""

from __future__ import annotations

import os
import re
from typing import Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

_client: Optional[object] = None
SAFE_KEY_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def _get_client():
    """Return a lazily-initialised boto3 S3 client pointed at R2."""
    global _client
    if _client is None:
        endpoint = os.environ["ORAMA_OBJECT_STORAGE_ENDPOINT"]
        _client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
    return _client


def _bucket() -> str:
    return os.environ["ORAMA_OBJECT_STORAGE_BUCKET"]


def validate_object_key(key: str) -> str:
    """Reject unsafe storage keys before passing them to the object-store client."""

    if (
        not key
        or not SAFE_KEY_SEGMENT.fullmatch(key)
        or "//" in key
        or ".." in key.split("/")
    ):
        raise ValueError("Object key is invalid.")
    return key


def upload_bytes(
    key: str, data: bytes, content_type: str = "application/octet-stream"
) -> None:
    """Upload raw bytes to R2 under the given key."""
    _get_client().put_object(
        Bucket=_bucket(),
        Key=validate_object_key(key),
        Body=data,
        ContentType=content_type,
    )


def download_bytes(key: str) -> bytes:
    """Download and return the raw bytes for the given key."""
    response = _get_client().get_object(Bucket=_bucket(), Key=validate_object_key(key))
    return response["Body"].read()


def generate_presigned_download_url(key: str, expires_in: int = 3600) -> str:
    """Return a short-lived presigned GET URL for the given key."""
    return _get_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": validate_object_key(key)},
        ExpiresIn=expires_in,
    )


def generate_presigned_upload_url(
    key: str, content_type: str, expires_in: int = 900
) -> str:
    """Return a short-lived presigned PUT URL for direct browser-to-R2 upload."""
    return _get_client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": _bucket(),
            "Key": validate_object_key(key),
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )


def key_exists(key: str) -> bool:
    """Return True if the given key exists in the bucket."""
    try:
        _get_client().head_object(Bucket=_bucket(), Key=validate_object_key(key))
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def delete_object(key: str) -> None:
    """Delete the object at the given key (no-op if it does not exist)."""
    _get_client().delete_object(Bucket=_bucket(), Key=validate_object_key(key))


def delete_prefix(prefix: str) -> int:
    """Delete every object under a validated job-scoped prefix and return its count."""

    prefix = validate_object_key(prefix.strip("/"))
    client = _get_client()
    deleted = 0
    continuation_token: str | None = None

    while True:
        request: dict[str, object] = {"Bucket": _bucket(), "Prefix": f"{prefix}/"}
        if continuation_token:
            request["ContinuationToken"] = continuation_token
        response = client.list_objects_v2(**request)
        object_keys = [item["Key"] for item in response.get("Contents", [])]
        if object_keys:
            client.delete_objects(
                Bucket=_bucket(),
                Delete={
                    "Objects": [{"Key": key} for key in object_keys],
                    "Quiet": True,
                },
            )
            deleted += len(object_keys)
        if not response.get("IsTruncated"):
            return deleted
        continuation_token = response.get("NextContinuationToken")
