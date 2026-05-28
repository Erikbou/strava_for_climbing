"""Artemis backend — FastAPI service that owns the Python pose pipeline,
schema bootstrap, and media serving.

The Next.js `web` service is the only intended caller. Routes that mutate
state require the shared ``X-Artemis-Service-Key`` header (configured via
the ``ARTEMIS_API_KEY`` env var on both services). Reads are public so the
browser can fetch highlight videos directly.

Endpoints
---------
- ``GET  /health`` — liveness probe.
- ``POST /schema/init`` — idempotent ``strava_climbing.db.init_db()``.
- ``POST /process-upload`` — multipart ``file`` + ``climber`` + ``color`` +
  ``gym`` + ``title`` + ``user_id``. Persists to ``data/raw/`` and runs the
  full pipeline. Returns ``{"attempt_id": int | null}``.
- ``GET  /media`` — range-aware static video streaming out of the configured
  media roots (same allowlist semantics as the previous web ``/api/media``).
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse


def _media_roots() -> list[Path]:
    raw = os.environ.get("ARTEMIS_MEDIA_ROOT") or "data"
    roots: list[Path] = []
    for piece in raw.split(","):
        s = piece.strip()
        if s:
            roots.append(Path(s).resolve())
    if not roots:
        roots.append(Path("data").resolve())
    return roots


def _require_service_key(
    x_artemis_service_key: str | None = Header(default=None),
) -> None:
    expected = os.environ.get("ARTEMIS_API_KEY")
    if not expected:
        # No key configured = open mode. Useful for local dev when nothing's
        # exposed publicly; in prod the deploy must always set ARTEMIS_API_KEY
        # on both web and api services.
        return
    if x_artemis_service_key != expected:
        raise HTTPException(status_code=401, detail="bad service key")


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Bootstrap the schema once before serving any request. Retries a few
    times so the api can start before postgres is fully reachable — Specific
    orders services but a cold-start can still race the listener."""
    _bootstrap_schema()
    yield


def _bootstrap_schema() -> None:
    from strava_climbing.db import init_db

    last_err: Exception | None = None
    for attempt_n in range(1, 11):
        try:
            init_db()
            print("schema: bootstrapped", file=sys.stderr)
            return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            wait = min(0.5 * attempt_n, 3.0)
            print(
                f"schema: init failed (attempt {attempt_n}): {exc!r}; retrying in {wait:.1f}s",
                file=sys.stderr,
            )
            time.sleep(wait)
    raise RuntimeError(f"schema bootstrap failed after 10 attempts: {last_err!r}")


app = FastAPI(title="artemis-api", version="0.1.0", lifespan=_lifespan)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

@app.post("/schema/init", dependencies=[Depends(_require_service_key)])
def schema_init() -> dict[str, str]:
    from strava_climbing.db import init_db

    init_db()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Upload + pipeline (async via background task + job table)
# ---------------------------------------------------------------------------

@app.post("/process-upload", dependencies=[Depends(_require_service_key)])
async def process_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    climber: str = Form(...),
    gym: str = Form(""),
    color: str | None = Form(None),
    title: str | None = Form(None),
    user_id: int | None = Form(None),
) -> JSONResponse:
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="empty file")
    sha = hashlib.sha256(raw_bytes).hexdigest()
    suffix = Path(file.filename or "upload.mp4").suffix.lower() or ".mp4"

    raw_dir = Path(os.environ.get("ARTEMIS_RAW_DIR", "data/raw")).resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{sha[:12]}{suffix}"
    raw_path.write_bytes(raw_bytes)

    payload = {
        "raw_path": str(raw_path),
        "climber": climber.strip(),
        "gym": gym.strip(),
        "color": (color or None),
        "title": (title.strip() if title else None),
        "user_id": user_id if isinstance(user_id, int) else None,
    }
    job_id = _create_job("process_upload", payload, user_id if isinstance(user_id, int) else None)

    background_tasks.add_task(_run_process_upload_job, job_id, payload)

    return JSONResponse({"job_id": job_id, "status": "queued"})


@app.get("/jobs/{job_id}")
def get_job(job_id: int) -> JSONResponse:
    job = _fetch_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JSONResponse(job)


def _create_job(kind: str, payload: dict[str, Any], user_id: int | None) -> int:
    import json

    from strava_climbing.db import connect

    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO job(kind, status, payload, user_id)
            VALUES (%s, 'queued', %s::jsonb, %s)
            RETURNING id
            """,
            (kind, json.dumps(payload), user_id),
        ).fetchone()
    if not row:
        raise RuntimeError("failed to insert job row")
    return int(row["id"])


def _fetch_job(job_id: int) -> dict[str, Any] | None:
    from strava_climbing.db import connect

    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, kind, status, attempt_id, error,
                   created_at, started_at, completed_at
              FROM job
             WHERE id = %s
            """,
            (job_id,),
        ).fetchone()
    if not row:
        return None
    # psycopg datetime / NULL → JSON.
    return {
        "id": row["id"],
        "kind": row["kind"],
        "status": row["status"],
        "attempt_id": row["attempt_id"],
        "error": row["error"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
    }


def _set_job_status(
    job_id: int,
    status: str,
    *,
    attempt_id: int | None = None,
    error: str | None = None,
) -> None:
    from strava_climbing.db import connect

    if status == "running":
        sql = "UPDATE job SET status = 'running', started_at = now() WHERE id = %s"
        params: tuple[Any, ...] = (job_id,)
    elif status == "ready":
        sql = (
            "UPDATE job SET status = 'ready', attempt_id = %s, completed_at = now() "
            "WHERE id = %s"
        )
        params = (attempt_id, job_id)
    elif status == "failed":
        sql = (
            "UPDATE job SET status = 'failed', error = %s, completed_at = now() "
            "WHERE id = %s"
        )
        params = (error, job_id)
    else:
        raise ValueError(f"unknown status {status}")
    with connect() as conn:
        conn.execute(sql, params)


def _run_process_upload_job(job_id: int, payload: dict[str, Any]) -> None:
    """Worker body — runs in the BackgroundTasks thread after the response is
    sent. Wraps every exception so a single bad upload can't kill the api."""
    _set_job_status(job_id, "running")
    try:
        attempt_id = _do_process_upload(payload)
    except Exception as exc:  # noqa: BLE001
        msg = f"{type(exc).__name__}: {exc}"
        print(f"job {job_id} failed: {msg}", file=sys.stderr)
        _set_job_status(job_id, "failed", error=msg)
        return
    _set_job_status(job_id, "ready", attempt_id=attempt_id)


def _do_process_upload(payload: dict[str, Any]) -> int | None:
    from strava_climbing import orchestrate
    from strava_climbing.db import connect

    raw_path = Path(payload["raw_path"])
    user_id = payload.get("user_id")

    attempt_id = orchestrate.process_uploaded_file(
        raw_path,
        climber_name=payload.get("climber") or "",
        color=payload.get("color") or None,
        gym=payload.get("gym") or "",
        title=payload.get("title"),
    )

    if attempt_id is not None and isinstance(user_id, int):
        try:
            with connect() as conn:
                conn.execute(
                    "UPDATE attempt SET user_id = %s WHERE id = %s",
                    (user_id, attempt_id),
                )
                conn.execute(
                    """
                    UPDATE climber SET user_id = %s
                     WHERE id = (SELECT climber_id FROM attempt WHERE id = %s)
                       AND user_id IS NULL
                    """,
                    (user_id, attempt_id),
                )
        except Exception as exc:  # noqa: BLE001
            print(f"warn: link user failed: {exc}", file=sys.stderr)

    if attempt_id is not None:
        try:
            _publish_attempt_media(attempt_id)
        except Exception as exc:  # noqa: BLE001
            print(f"warn: media publish failed: {exc}", file=sys.stderr)

    return attempt_id


# ---------------------------------------------------------------------------
# Storage publishing — mirror highlight/overlay to storage.media + rewrite
# the DB path so subsequent reads come from object storage.
# ---------------------------------------------------------------------------

def _publish_attempt_media(attempt_id: int) -> None:
    from strava_climbing import storage_client
    from strava_climbing.db import connect

    if not storage_client.is_enabled():
        return

    with connect() as conn:
        row = conn.execute(
            "SELECT highlight_path, overlay_path FROM attempt WHERE id = %s",
            (attempt_id,),
        ).fetchone()
    if not row:
        return

    updates: dict[str, str] = {}
    for column in ("highlight_path", "overlay_path"):
        value = row[column]
        if not value or _is_object_uri(value):
            continue
        local = Path(value)
        if not local.exists() or not local.is_file():
            continue
        kind = "highlights" if column == "highlight_path" else "overlays"
        key = f"{kind}/{local.name}"
        try:
            uri = storage_client.upload_file(local, key, content_type="video/mp4")
        except Exception as exc:  # noqa: BLE001
            print(f"warn: upload {column} failed: {exc}", file=sys.stderr)
            continue
        updates[column] = uri
        # Best-effort local cleanup; the api container's disk is ephemeral.
        try:
            local.unlink()
        except OSError:
            pass

    if not updates:
        return
    set_clause = ", ".join(f"{col} = %s" for col in updates)
    params = (*updates.values(), attempt_id)
    with connect() as conn:
        conn.execute(f"UPDATE attempt SET {set_clause} WHERE id = %s", params)


def _is_object_uri(value: str) -> bool:
    return value.startswith("s3://") or value.startswith("https://")


# ---------------------------------------------------------------------------
# Media — range-aware static streaming
# ---------------------------------------------------------------------------

_RANGE_RE = re.compile(r"bytes=(\d+)-(\d+)?")


def _safe_resolve(requested: str) -> Path | None:
    candidate = Path(requested).resolve()
    for root in _media_roots():
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if not candidate.exists() or not candidate.is_file():
            return None
        return candidate
    return None


def _stream_range(path: Path, start: int, end: int, chunk: int = 64 * 1024):
    with path.open("rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            data = f.read(min(chunk, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def _stream_full(path: Path, chunk: int = 64 * 1024):
    with path.open("rb") as f:
        while True:
            data = f.read(chunk)
            if not data:
                break
            yield data


@app.get("/media")
def media(
    request: Request,
    path: str = Query(...),
) -> Response:
    # If the caller hands us an object-store URI, 302 to a short-lived
    # presigned URL — the browser streams from object storage directly.
    if path.startswith("s3://"):
        from strava_climbing import storage_client

        if not storage_client.is_enabled():
            raise HTTPException(status_code=500, detail="storage not configured")
        _bucket, key = storage_client.parse_s3_uri(path)
        url = storage_client.presigned_url(key)
        return RedirectResponse(url, status_code=307)

    resolved = _safe_resolve(path)
    if resolved is None:
        raise HTTPException(status_code=404, detail="not found")
    total = resolved.stat().st_size
    range_hdr = request.headers.get("range")
    headers = {
        "content-type": "video/mp4",
        "accept-ranges": "bytes",
        "cache-control": "private, max-age=60",
    }
    if range_hdr:
        m = _RANGE_RE.search(range_hdr)
        if not m:
            raise HTTPException(status_code=416, detail="bad range")
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else total - 1
        if start >= total or end >= total:
            raise HTTPException(status_code=416, detail="range out of bounds")
        headers["content-range"] = f"bytes {start}-{end}/{total}"
        headers["content-length"] = str(end - start + 1)
        return StreamingResponse(
            _stream_range(resolved, start, end),
            status_code=206,
            headers=headers,
        )
    headers["content-length"] = str(total)
    return StreamingResponse(_stream_full(resolved), status_code=200, headers=headers)


# ---------------------------------------------------------------------------
# Entrypoint helpers
# ---------------------------------------------------------------------------

def run() -> None:
    """``python -m apps.api`` boot helper for local dev."""
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "apps.api.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()


def _placate_linter_unused(*_args: Any) -> None:
    """Avoid B008/UP/etc. on the module-level Depends sentinel."""
