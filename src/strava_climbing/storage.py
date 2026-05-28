"""Supabase Storage wrapper for video blobs.

The structured data lives in Postgres (see ``db.py``); video files live in
Supabase Storage buckets. Three buckets, one per pipeline stage:

- ``raw`` — original uploads from climbers (written by the frontend, read
  by ``ingest.py``).
- ``normalized`` — ffmpeg-normalized 720p/30fps mp4s (written by
  ``ingest.py``, read by the frontend / Streamlit).
- ``overlays`` — pose-skeleton overlay clips (written by ``orchestrate.py``,
  read by the frontend / Streamlit).

Bucket names are env-driven. When a bucket env var is unset the
corresponding kind is treated as "not configured" — the pipeline falls back
to local-filesystem-only behavior for that stage. This keeps local dev
working without Supabase Storage credentials.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from .db import connect

Kind = Literal["raw", "normalized", "overlays"]

_ENV_VARS: dict[Kind, str] = {
    "raw": "SUPABASE_STORAGE_RAW_BUCKET",
    "normalized": "SUPABASE_STORAGE_NORMALIZED_BUCKET",
    "overlays": "SUPABASE_STORAGE_OVERLAYS_BUCKET",
}

_CONTENT_TYPE = "video/mp4"


def bucket_name(kind: Kind) -> str | None:
    """Return the configured bucket name for ``kind`` or ``None`` if unset."""
    return os.environ.get(_ENV_VARS[kind]) or None


def bucket_configured(kind: Kind) -> bool:
    return bucket_name(kind) is not None


def _bucket(kind: Kind):
    name = bucket_name(kind)
    if name is None:
        raise RuntimeError(
            f"{_ENV_VARS[kind]} is not set — "
            f"cannot use Supabase Storage for kind={kind!r}"
        )
    return connect().storage.from_(name)


def upload_file(local_path: Path, key: str, *, kind: Kind) -> str:
    """Upload ``local_path`` to ``kind`` bucket under ``key``. Returns ``key``.

    Uses upsert semantics — re-uploading the same key overwrites. Combined
    with the ingest pipeline's SHA-based dedup, this gives idempotency on
    re-runs: the same source file produces the same key, and the upload
    short-circuits to a no-op-shaped overwrite.
    """
    with open(local_path, "rb") as f:
        _bucket(kind).upload(
            path=key,
            file=f,
            file_options={
                "content-type": _CONTENT_TYPE,
                "upsert": "true",
            },
        )
    return key


def download_file(key: str, dst: Path, *, kind: Kind) -> Path:
    """Download ``key`` from ``kind`` bucket to ``dst``. Returns ``dst``."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = _bucket(kind).download(key)
    dst.write_bytes(data)
    return dst


def list_keys(kind: Kind, *, prefix: str = "") -> list[str]:
    """List object keys in ``kind`` bucket, optionally filtered by prefix."""
    res = _bucket(kind).list(path=prefix or None)
    return [obj["name"] for obj in res if obj.get("name")]


def signed_url(key: str, *, kind: Kind, expires_in: int = 3600) -> str:
    """Mint a time-limited URL the frontend can pass to ``<video src>``."""
    res = _bucket(kind).create_signed_url(path=key, expires_in=expires_in)
    # supabase-py returns {"signedURL": "..."} on success.
    url = res.get("signedURL") or res.get("signed_url")
    if not url:
        raise RuntimeError(f"signed URL response missing 'signedURL': {res!r}")
    return url


__all__ = [
    "Kind",
    "bucket_configured",
    "bucket_name",
    "download_file",
    "list_keys",
    "signed_url",
    "upload_file",
]
