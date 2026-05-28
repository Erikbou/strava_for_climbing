"""SQLite backend integration tests.

The Supabase backend is exercised against a live project — out of scope here.
These tests force ``STRAVA_CLIMBING_BACKEND=sqlite`` and point ``DATA_ROOT``
at a tmp dir so each test gets a fresh database.
"""

from __future__ import annotations

import importlib
import sqlite3
from collections.abc import Iterator

import pytest

from strava_climbing.provenance import RouteSource
from strava_climbing.schema import Attempt, Route, Video


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch) -> Iterator:
    monkeypatch.setenv("STRAVA_CLIMBING_BACKEND", "sqlite")
    monkeypatch.setenv("STRAVA_CLIMBING_DATA_ROOT", str(tmp_path))
    for k in (
        "NEXT_PUBLIC_SUPABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_KEY",
        "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    ):
        monkeypatch.delenv(k, raising=False)

    import strava_climbing._backend_sqlite as backend
    import strava_climbing.config.paths as paths_mod
    import strava_climbing.db as db_mod

    backend._conn.cache_clear()
    importlib.reload(paths_mod)
    importlib.reload(backend)
    importlib.reload(db_mod)

    db_mod.init_db()
    yield db_mod
    backend._conn.cache_clear()


def test_upsert_climber_idempotent(sqlite_db):
    a = sqlite_db.upsert_climber("Erik")
    b = sqlite_db.upsert_climber("Erik")
    assert a == b


def test_video_dedup_by_source_sha256(sqlite_db):
    v1 = Video(None, "/raw/a.mov", "a.mp4", "sha-abc", 30.0, 1280, 720, 30.0, "ok", None)
    id1 = sqlite_db.upsert_video(v1)
    v2 = Video(None, "/raw/b.mov", "b.mp4", "sha-abc", 30.0, 1280, 720, 30.0, "ok", None)
    id2 = sqlite_db.upsert_video(v2)
    assert id1 == id2


def test_manual_route_trigger_blocks_overwrite(sqlite_db):
    wall_id = sqlite_db.find_or_create_wall("Klättercentret")
    climber_id = sqlite_db.upsert_climber("Niklavs")
    video_id = sqlite_db.upsert_video(
        Video(None, "/raw/x.mov", "x.mp4", "sha-x", 30.0, 1280, 720, 30.0, "ok", None),
    )
    route_id = sqlite_db.upsert_route(Route(id=None, wall_id=wall_id, origin=RouteSource.MANUAL))
    sqlite_db.upsert_attempt(
        Attempt(
            id=None, video_id=video_id, climber_id=climber_id, route_id=route_id,
            start_frame=0, end_frame=100, time_seconds=3.3,
            send=True, attempts_count=1,
            route_source=RouteSource.MANUAL, config_hash="cfg-1",
        ),
    )
    import strava_climbing._backend_sqlite as backend
    conn = backend._conn()  # internal access for the trigger probe
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE attempt SET route_source = 'auto' WHERE route_id = ?", (route_id,)
        )


def test_leaderboard_orders_sends_first(sqlite_db):
    wall_id = sqlite_db.find_or_create_wall("K")
    erik = sqlite_db.upsert_climber("Erik")
    emil = sqlite_db.upsert_climber("Emil")
    video_id = sqlite_db.upsert_video(
        Video(None, "/raw/x.mov", "x.mp4", "sha-x", 30.0, 1280, 720, 30.0, "ok", None),
    )
    route_id = sqlite_db.upsert_route(Route(id=None, wall_id=wall_id, origin=RouteSource.MANUAL))
    for climber_id, start, end, t, send in [
        (erik, 0, 100, 5.0, True),
        (emil, 200, 350, 4.0, False),
        (emil, 400, 550, 3.0, True),
    ]:
        sqlite_db.upsert_attempt(
            Attempt(
                id=None, video_id=video_id, climber_id=climber_id, route_id=route_id,
                start_frame=start, end_frame=end, time_seconds=t,
                send=send, attempts_count=1,
                route_source=RouteSource.MANUAL, config_hash="cfg",
            ),
        )
    rows = sqlite_db.leaderboard(route_id)
    assert [r["climber_name"] for r in rows] == ["Emil", "Erik", "Emil"]
    assert rows[0]["send"] == 1
    assert rows[0]["time_seconds"] == 3.0


def test_storage_helpers_are_local_in_sqlite_mode(sqlite_db, tmp_path):
    overlay = tmp_path / "overlays" / "5_a0.mp4"
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_bytes(b"placeholder")
    key = sqlite_db.upload_overlay(overlay)
    assert key == "5_a0.mp4"
    assert sqlite_db.overlay_exists(key)
    assert sqlite_db.overlay_local_path(key) == overlay
    assert sqlite_db.overlay_playback_source(key) == overlay
