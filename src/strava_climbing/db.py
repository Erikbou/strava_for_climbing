"""Supabase client + thin repositories.

The pipeline used to talk to a local SQLite file via ``sqlite3.connect()``;
it now talks to a Supabase Postgres project via PostgREST. Schema DDL is
applied separately — see ``supabase/migrations/0001_initial_schema.sql``.

Credentials are read from the package-local ``.env`` (or process env). The
client is cached so callers can keep using ``connect()`` without paying
TCP setup on every call.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from supabase import Client, create_client

from .provenance import RouteSource
from .schema import Attempt, Route, Video


def _load_dotenv_once() -> None:
    """Populate os.environ from src/strava_climbing/.env if present.

    Kept dependency-free — full python-dotenv is overkill for two keys.
    """
    candidates = [
        Path(__file__).resolve().parent / ".env",
        Path.cwd() / ".env",
    ]
    for p in candidates:
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv_once()


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
            "for write access) in src/strava_climbing/.env"
        )
    return url, key


@lru_cache(maxsize=1)
def _cached_client() -> Client:
    url, key = _resolve_credentials()
    return create_client(url, key)


def connect(*_args: Any, read_only: bool = False, **_kwargs: Any) -> Client:
    """Return the cached Supabase client.

    The ``*_args`` / ``**_kwargs`` exist purely so this remains a drop-in for
    the old ``connect(path)`` signature called from older entry points.
    ``read_only`` is currently advisory — write protection lives in Postgres
    RLS rather than the client.
    """
    del read_only  # noted; no separate read-only client at the moment
    return _cached_client()


def init_db(*_args: Any, **_kwargs: Any) -> None:
    """No-op for Supabase.

    Schema is applied out-of-band via ``supabase/migrations/0001_initial_schema.sql``
    (run it in the Supabase SQL editor or via ``supabase db push``). Kept as a
    function so existing call sites in ``ingest.py`` and ``orchestrate.py`` need
    no changes.
    """
    return None


# --- Repository helpers (thin) ----------------------------------------------


def upsert_climber(client: Client, name: str, aliases: list[str] | None = None) -> int:
    res = (
        client.table("climber")
        .upsert(
            {"name": name, "aliases": aliases or []},
            on_conflict="name",
        )
        .execute()
    )
    return res.data[0]["id"]


def upsert_video(client: Client, v: Video) -> int:
    res = (
        client.table("video")
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
                "source_bucket_key": v.source_bucket_key,
                "normalized_bucket_key": v.normalized_bucket_key,
            },
            on_conflict="source_sha256",
        )
        .execute()
    )
    return res.data[0]["id"]


def get_video_by_sha(client: Client, sha256: str) -> Video | None:
    res = (
        client.table("video")
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
        source_bucket_key=row.get("source_bucket_key"),
        normalized_bucket_key=row.get("normalized_bucket_key"),
    )


def upsert_attempt(client: Client, a: Attempt) -> int:
    res = (
        client.table("attempt")
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


def upsert_route(client: Client, r: Route) -> int:
    res = (
        client.table("route")
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


def update_attempt_smoothness_pct(
    client: Client, attempt_id: int, smoothness_pct: float | None
) -> None:
    client.table("attempt").update({"smoothness_pct": smoothness_pct}).eq(
        "id", attempt_id
    ).execute()


def find_or_create_wall(client: Client, gym_name: str) -> int:
    existing = (
        client.table("wall")
        .select("id")
        .eq("gym_name", gym_name)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]["id"]
    res = client.table("wall").insert({"gym_name": gym_name}).execute()
    return res.data[0]["id"]


def find_route(client: Client, wall_id: int, color: str | None) -> int | None:
    q = client.table("route").select("id").eq("wall_id", wall_id)
    q = q.is_("color", "null") if color is None else q.eq("color", color)
    res = q.limit(1).execute()
    return res.data[0]["id"] if res.data else None


def list_attempts_for_video(client: Client, video_id: int) -> list[dict[str, Any]]:
    res = (
        client.table("attempt")
        .select("id, smoothness_raw, route_id")
        .eq("video_id", video_id)
        .execute()
    )
    return res.data


def list_ok_videos(client: Client) -> list[dict[str, Any]]:
    res = (
        client.table("video")
        .select("id, source_path, normalized_path, height, fps")
        .eq("ingest_status", "ok")
        .execute()
    )
    return res.data


def attempts_for_route(client: Client, route_id: int) -> list[dict[str, Any]]:
    res = (
        client.table("attempt")
        .select("id, smoothness_raw")
        .eq("route_id", route_id)
        .not_.is_("smoothness_raw", "null")
        .order("id")
        .execute()
    )
    return res.data


def distinct_route_ids_with_attempts(client: Client) -> list[int]:
    res = (
        client.table("attempt")
        .select("route_id")
        .not_.is_("route_id", "null")
        .execute()
    )
    return sorted({row["route_id"] for row in res.data})


def leaderboard(client: Client, route_id: int) -> list[dict[str, Any]]:
    res = (
        client.table("attempt")
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


def list_routes(client: Client) -> list[dict[str, Any]]:
    res = (
        client.table("route_with_attempt_counts")
        .select("id, color, origin, sample_frame_path, attempt_count")
        .order("attempt_count", desc=True)
        .execute()
    )
    return res.data


def overlay_paths_in_use(client: Client) -> list[str]:
    res = (
        client.table("attempt")
        .select("overlay_path")
        .not_.is_("overlay_path", "null")
        .execute()
    )
    return [row["overlay_path"] for row in res.data]


def route_sample_frame_paths(client: Client) -> list[str]:
    res = (
        client.table("route")
        .select("sample_frame_path")
        .not_.is_("sample_frame_path", "null")
        .execute()
    )
    return [row["sample_frame_path"] for row in res.data]


def get_attempt_detail(client: Client, attempt_id: int) -> dict[str, Any] | None:
    res = (
        client.table("attempt")
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


def get_route_with_wall(client: Client, route_id: int) -> dict[str, Any] | None:
    res = (
        client.table("route")
        .select("id, color, origin, sample_frame_path, cluster_confidence, "
                "wall_id, wall(gym_name)")
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


__all__ = [
    "RouteSource",
    "attempts_for_route",
    "connect",
    "distinct_route_ids_with_attempts",
    "find_or_create_wall",
    "find_route",
    "get_attempt_detail",
    "get_route_with_wall",
    "get_video_by_sha",
    "init_db",
    "leaderboard",
    "list_attempts_for_video",
    "list_ok_videos",
    "list_routes",
    "overlay_paths_in_use",
    "route_sample_frame_paths",
    "update_attempt_smoothness_pct",
    "upsert_attempt",
    "upsert_climber",
    "upsert_route",
    "upsert_video",
]
