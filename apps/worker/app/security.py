"""Shared-secret authentication for internal endpoints."""

from __future__ import annotations

import os
import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

SHARED_SECRET_HEADER = "X-Orama-Worker-Secret"
DEFAULT_SHARED_SECRET = "changeme-local-dev-secret"
LOCAL_ENV_NAMES = {"local", "dev", "development", "test"}


def get_expected_shared_secret() -> str:
    """Resolve the expected secret, allowing the placeholder only for local/dev use."""

    configured_secret = os.getenv("ORAMA_WORKER_SHARED_SECRET")
    if configured_secret:
        return configured_secret

    runtime_env = os.getenv("ORAMA_RUNTIME_ENV", "").strip().lower()
    if runtime_env in LOCAL_ENV_NAMES and not os.getenv("HF_SPACE_ID"):
        return DEFAULT_SHARED_SECRET

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Worker shared secret is not configured. Set ORAMA_WORKER_SHARED_SECRET; "
            "the placeholder local-dev secret is only allowed when ORAMA_RUNTIME_ENV "
            "is explicitly set to a local/dev value outside production-like deployments."
        ),
    )


async def verify_shared_secret(
    x_orama_worker_secret: Annotated[
        str | None, Header(alias=SHARED_SECRET_HEADER)
    ] = None,
) -> None:
    """Validate the internal shared secret header.

    The default fallback secret exists only to make local synthetic development easier.
    It must not be treated as a production credential.
    """

    expected_secret = get_expected_shared_secret()
    provided_secret = x_orama_worker_secret or ""
    if not secrets.compare_digest(provided_secret, expected_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid shared secret for internal worker endpoint.",
        )
