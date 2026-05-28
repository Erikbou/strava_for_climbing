"""Supabase backend: Postgres via PostgREST + Storage buckets for .mp4 files.

The schema is applied out-of-band via ``supabase/migrations/0001_initial_schema.sql``
(SQL editor in the dashboard or ``supabase db push`` with the CLI).

DB columns ``video.normalized_path`` and ``attempt.overlay_path`` store the
**object key** (basename of the file) — never a filesystem path. That way the
SQLite fallback in ``_backend_sqlite.py`` can use the same column semantics:
basename resolves to ``data/normalized/<key>`` locally, and to a bucket object
in Supabase mode.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from supabase import Client, create_client

from .config import paths as P
from .provenance import RouteSource  # re-exported below
from .schema import Attempt, Route, Video

_NORMALIZED_BUCKET = "normalized"
_OVERLAY_BUCKET = "overlays"


def _resolve_credentials() -> tuple[str, str]:
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    if not url or not key:
        raise RuntimeError(
            "Missing Supabase credentials. Set NEXT_PUBLIC_SUPABASE_URL and "
            "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY (or SUPABASE_SERVICE_ROLE_KEY "
            "for write access) in src/strava_climbing/.env, or set "
            "STRAVA_CLIMBING_BACKEND=sqlite to use the offline fallback."
        )
    return url, key


@lru_cache(maxsize=1)
def _client() -> Client:
    url, key = _resolve_credentials()
    return create_client(url, key)


def init_db() -> None:
    """No-op for Supabase. Schema is applied via supabase/migrations/."""
    return None


# --- Climber / video / attempt / route writes ------------------------------


def upsert_climber(name: str, aliases: list[str] | None = None) -> int:
    res = (
        _client()
        .table("climber")
        .upsert({"name": name, "aliases": aliases or []}, on_conflict="name")
        .execute()
    )
    return res.data[0]["id"]


def upsert_video(v: Video) -> int:
    res = (
        _client()
        .table("video")
        .upsert(
            {
                "source_path": v.source_path,
                "normalized_path": v.normalized_path,
                "source_sha256": v.source_sha256,
                "duration_seconds": v.duration_seconds,
                "width": v.width,
                "height": v.height,
                "fps": v.fps,
                "ingest_status": v.ingest_status,
                "ingest_report": v.ingest_report,
            },
            on_conflict="source_sha256",
        )
        .execute()
    )
    return res.data[0]["id"]


def get_video_by_sha(sha256: str) -> Video | None:
    res = (
        _client()
        .table("video")
        .select("*")
        .eq("source_sha256", sha256)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    row = res.data[0]
    return Video(
        id=row["id"],
        source_path=row["source_path"],
        normalized_path=row["normalized_path"],
        source_sha256=row["source_sha256"],
        duration_seconds=row["duration_seconds"],
        width=row["width"],
        height=row["height"],
        fps=row["fps"],
        ingest_status=row["ingest_status"],
        ingest_report=row["ingest_report"],
    )


def upsert_attempt(a: Attempt) -> int:
    res = (
        _client()
        .table("attempt")
        .upsert(
            {
                "climber_id": a.climber_id,
                "route_id": a.route_id,
                "video_id": a.video_id,
                "start_frame": a.start_frame,
                "end_frame": a.end_frame,
                "time_seconds": a.time_seconds,
                "smoothness_raw": a.smoothness_raw,
                "smoothness_pct": a.smoothness_pct,
                "send": bool(a.send),
                "attempts_count": a.attempts_count,
                "route_source": str(a.route_source),
                "overlay_path": a.overlay_path,
                "config_hash": a.config_hash,
            },
            on_conflict="video_id,start_frame,end_frame",
        )
        .execute()
    )
    return res.data[0]["id"]


def upsert_route(r: Route) -> int:
    res = (
        _client()
        .table("route")
        .insert(
            {
                "wall_id": r.wall_id,
                "color": r.color,
                "sample_frame_path": r.sample_frame_path,
                "hold_layout": r.hold_layout,
                "origin": str(r.origin),
                "cluster_confidence": r.cluster_confidence,
            }
        )
        .execute()
    )
    return res.data[0]["id"]


def update_attempt_smoothness_pct(attempt_id: int, smoothness_pct: float | None) -> None:
    _client().table("attempt").update({"smoothness_pct": smoothness_pct}).eq(
        "id", attempt_id
    ).execute()


def find_or_create_wall(gym_name: str) -> int:
    existing = (
        _client()
        .table("wall")
        .select("id")
        .eq("gym_name", gym_name)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]["id"]
    res = _client().table("wall").insert({"gym_name": gym_name}).execute()
    return res.data[0]["id"]


def find_route(wall_id: int, color: str | None) -> int | None:
    q = _client().table("route").select("id").eq("wall_id", wall_id)
    q = q.is_("color", "null") if color is None else q.eq("color", color)
    res = q.limit(1).execute()
    return res.data[0]["id"] if res.data else None


# --- Reads -----------------------------------------------------------------


def list_ok_videos() -> list[dict[str, Any]]:
    res = (
        _client()
        .table("video")
        .select("id, source_path, normalized_path, height, fps")
        .eq("ingest_status", "ok")
        .execute()
    )
    return res.data


def attempts_for_route(route_id: int) -> list[dict[str, Any]]:
    res = (
        _client()
        .table("attempt")
        .select("id, smoothness_raw")
        .eq("route_id", route_id)
        .not_.is_("smoothness_raw", "null")
        .order("id")
        .execute()
    )
    return res.data


def distinct_route_ids_with_attempts() -> list[int]:
    res = (
        _client()
        .table("attempt")
        .select("route_id")
        .not_.is_("route_id", "null")
        .execute()
    )
    return sorted({row["route_id"] for row in res.data})


def leaderboard(route_id: int) -> list[dict[str, Any]]:
    res = (
        _client()
        .table("attempt")
        .select(
            "id, time_seconds, smoothness_pct, send, overlay_path, attempts_count, "
            "climber(name)"
        )
        .eq("route_id", route_id)
        .order("send", desc=True)
        .order("time_seconds", desc=False)
        .execute()
    )
    out: list[dict[str, Any]] = []
    for r in res.data:
        climber = r.get("climber")
        out.append(
            {
                "attempt_id": r["id"],
                "climber_name": climber["name"] if climber else None,
                "time_seconds": r["time_seconds"],
                "smoothness_pct": r["smoothness_pct"],
                "send": 1 if r["send"] else 0,
                "overlay_path": r["overlay_path"],
                "attempts_count": r["attempts_count"],
            }
        )
    return out


def list_routes() -> list[dict[str, Any]]:
    res = (
        _client()
        .table("route_with_attempt_counts")
        .select("id, color, origin, sample_frame_path, attempt_count")
        .order("attempt_count", desc=True)
        .execute()
    )
    return res.data


def overlay_paths_in_use() -> list[str]:
    res = (
        _client()
        .table("attempt")
        .select("overlay_path")
        .not_.is_("overlay_path", "null")
        .execute()
    )
    return [row["overlay_path"] for row in res.data]


def route_sample_frame_paths() -> list[str]:
    res = (
        _client()
        .table("route")
        .select("sample_frame_path")
        .not_.is_("sample_frame_path", "null")
        .execute()
    )
    return [row["sample_frame_path"] for row in res.data]


def get_attempt_detail(attempt_id: int) -> dict[str, Any] | None:
    res = (
        _client()
        .table("attempt")
        .select(
            "*, "
            "climber(name), "
            "route(color, wall(gym_name)), "
            "video(normalized_path)"
        )
        .eq("id", attempt_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    row = res.data[0]
    climber = row.pop("climber", None)
    route = row.pop("route", None)
    video = row.pop("video", None)
    flat = dict(row)
    flat["climber_name"] = climber["name"] if climber else None
    flat["route_color"] = route["color"] if route else None
    flat["gym_name"] = route["wall"]["gym_name"] if route and route.get("wall") else None
    flat["normalized_path"] = video["normalized_path"] if video else None
    return flat


def get_route_with_wall(route_id: int) -> dict[str, Any] | None:
    res = (
        _client()
        .table("route")
        .select(
            "id, color, origin, sample_frame_path, cluster_confidence, "
            "wall_id, wall(gym_name)"
        )
        .eq("id", route_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    row = res.data[0]
    wall = row.pop("wall", None)
    flat = dict(row)
    flat["gym_name"] = wall["gym_name"] if wall else None
    return flat


# --- Object storage -------------------------------------------------------


def _upload(bucket: str, local_path: Path) -> str:
    """Upload a file to a public bucket. The object key is its basename."""
    key = local_path.name
    with open(local_path, "rb") as fh:
        data = fh.read()
    # ``upsert=true`` lets re-runs overwrite stale renders without raising.
    _client().storage.from_(bucket).upload(
        path=key,
        file=data,
        file_options={"content-type": "video/mp4", "upsert": "true"},
    )
    return key


def upload_normalized(local_path: Path) -> str:
    return _upload(_NORMALIZED_BUCKET, local_path)


def upload_overlay(local_path: Path) -> str:
    return _upload(_OVERLAY_BUCKET, local_path)


def normalized_local_path(key: str) -> Path:
    return P.NORMALIZED_DIR / key


def overlay_local_path(key: str) -> Path:
    return P.OVERLAYS_DIR / key


def _public_url(bucket: str, key: str) -> str:
    return _client().storage.from_(bucket).get_public_url(key)


def overlay_playback_source(key: str) -> str:
    """Streamable URL for ``st.video``."""
    return _public_url(_OVERLAY_BUCKET, key)


def normalized_playback_source(key: str) -> str:
    return _public_url(_NORMALIZED_BUCKET, key)


def _object_exists(bucket: str, key: str) -> bool:
    """Use ``list()`` over the parent prefix; cheap because our keys are flat."""
    try:
        entries = _client().storage.from_(bucket).list()
    except Exception:
        return False
    names = {e.get("name") for e in entries or []}
    return key in names


def overlay_exists(key: str) -> bool:
    return _object_exists(_OVERLAY_BUCKET, key)


def normalized_exists(key: str) -> bool:
    return _object_exists(_NORMALIZED_BUCKET, key)


__all__ = [
    "RouteSource",
    "attempts_for_route",
    "distinct_route_ids_with_attempts",
    "find_or_create_wall",
    "find_route",
    "get_attempt_detail",
    "get_route_with_wall",
    "get_video_by_sha",
    "init_db",
    "leaderboard",
    "list_ok_videos",
    "list_routes",
    "normalized_exists",
    "normalized_local_path",
    "normalized_playback_source",
    "overlay_exists",
    "overlay_local_path",
    "overlay_paths_in_use",
    "overlay_playback_source",
    "route_sample_frame_paths",
    "update_attempt_smoothness_pct",
    "upload_normalized",
    "upload_overlay",
    "upsert_attempt",
    "upsert_climber",
    "upsert_route",
    "upsert_video",
]
