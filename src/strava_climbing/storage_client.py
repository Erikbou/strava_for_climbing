"""S3-compatible object storage helpers.

Wraps boto3 with credentials/endpoint pulled from ``S3_ENDPOINT``,
``S3_ACCESS_KEY``, ``S3_SECRET_KEY``, ``S3_BUCKET`` — the env vars wired up
in ``specific.hcl``. Use ``upload_file`` to push artefacts (e.g. overlay
MP4s) and ``presigned_url`` to fetch them for playback.

Filesystem paths (under ``data/``) remain the source of truth during the
pipeline run; S3 mirroring is opt-in and called by callers only when
``S3_BUCKET`` is set.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_DEFAULT_REGION = "us-east-1"  # MinIO ignores this but boto3 requires a value


def is_enabled() -> bool:
    """True iff all four S3_* env vars are present and non-empty."""
    return all(os.environ.get(k) for k in ("S3_ENDPOINT", "S3_ACCESS_KEY", "S3_SECRET_KEY", "S3_BUCKET"))


def _client() -> Any:
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name=_DEFAULT_REGION,
        config=_boto_config(),
    )


def _boto_config() -> Any:
    from botocore.config import Config

    # `forcePathStyle` equivalent — required for MinIO / local S3-compatibles.
    return Config(s3={"addressing_style": "path"}, signature_version="s3v4")


def upload_file(local_path: str | Path, key: str, *, content_type: str | None = None) -> str:
    """Upload ``local_path`` to ``S3_BUCKET`` at ``key``. Returns the s3:// URI."""
    extra: dict[str, str] = {}
    if content_type:
        extra["ContentType"] = content_type
    _client().upload_file(str(local_path), os.environ["S3_BUCKET"], key, ExtraArgs=extra or None)
    return f"s3://{os.environ['S3_BUCKET']}/{key}"


def presigned_url(key: str, *, expires_in: int = 3600) -> str:
    """Generate a time-limited URL the browser can fetch directly."""
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": os.environ["S3_BUCKET"], "Key": key},
        ExpiresIn=expires_in,
    )


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Split ``s3://bucket/key/with/slashes`` into ``(bucket, key)``."""
    if not uri.startswith("s3://"):
        raise ValueError(f"not an s3 URI: {uri}")
    rest = uri[len("s3://") :]
    bucket, _, key = rest.partition("/")
    if not bucket or not key:
        raise ValueError(f"malformed s3 URI: {uri}")
    return bucket, key


__all__ = ["is_enabled", "parse_s3_uri", "presigned_url", "upload_file"]
