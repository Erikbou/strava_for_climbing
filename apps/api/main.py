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
from pathlib import Path
from typing import Any

from fastapi import (
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
from fastapi.responses import JSONResponse, Response, StreamingResponse


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


app = FastAPI(title="artemis-api", version="0.1.0")


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
# Upload + pipeline
# ---------------------------------------------------------------------------

@app.post("/process-upload", dependencies=[Depends(_require_service_key)])
async def process_upload(
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

    from strava_climbing import orchestrate
    from strava_climbing.db import connect

    attempt_id = orchestrate.process_uploaded_file(
        raw_path,
        climber_name=climber.strip(),
        color=(color or None),
        gym=gym.strip(),
        title=(title.strip() if title else None),
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

    return JSONResponse({"attempt_id": attempt_id})


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
