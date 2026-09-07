"""Cloudflare R2 / S3-compatible object storage client for the ORAMA worker."""

from __future__ import annotations

import os
from typing import Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

_client: Optional[object] = None


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


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    """Upload raw bytes to R2 under the given key."""
    _get_client().put_object(
        Bucket=_bucket(),
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def download_bytes(key: str) -> bytes:
    """Download and return the raw bytes for the given key."""
    response = _get_client().get_object(Bucket=_bucket(), Key=key)
    return response["Body"].read()


def generate_presigned_download_url(key: str, expires_in: int = 3600) -> str:
    """Return a short-lived presigned GET URL for the given key."""
    return _get_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": key},
        ExpiresIn=expires_in,
    )


def generate_presigned_upload_url(key: str, content_type: str, expires_in: int = 900) -> str:
    """Return a short-lived presigned PUT URL for direct browser-to-R2 upload."""
    return _get_client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": _bucket(),
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )


def key_exists(key: str) -> bool:
    """Return True if the given key exists in the bucket."""
    try:
        _get_client().head_object(Bucket=_bucket(), Key=key)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def delete_object(key: str) -> None:
    """Delete the object at the given key (no-op if it does not exist)."""
    _get_client().delete_object(Bucket=_bucket(), Key=key)
