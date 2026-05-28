"""Schema + trigger integration tests using an in-memory SQLite database."""

from __future__ import annotations

import sqlite3

import pytest

from strava_climbing.db import (
    SCHEMA_SQL,
    leaderboard,
    upsert_attempt,
    upsert_climber,
    upsert_route,
    upsert_video,
)
from strava_climbing.provenance import RouteSource
from strava_climbing.schema import Attempt, Route, Video


def _mem() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    return conn


def test_schema_creates_cleanly():
    conn = _mem()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert tables == {"climber", "video", "wall", "route", "attempt", "hold"}


def test_upsert_climber_idempotent():
    conn = _mem()
    a = upsert_climber(conn, "Erik")
    b = upsert_climber(conn, "Erik")
    assert a == b


def test_video_dedup_by_source_sha256():
    conn = _mem()
    v1 = Video(None, "/raw/a.mov", "/norm/a.mp4", "sha-abc", 30.0, 1280, 720, 30.0, "ok", None)
    id1 = upsert_video(conn, v1)
    # Same sha, different paths -> upsert should reuse the id.
    v2 = Video(None, "/raw/b.mov", "/norm/b.mp4", "sha-abc", 30.0, 1280, 720, 30.0, "ok", None)
    id2 = upsert_video(conn, v2)
    assert id1 == id2


def test_manual_route_trigger_blocks_overwrite():
    conn = _mem()
    conn.execute("INSERT INTO wall(gym_name) VALUES ('Klättercentret')")
    wall_id = conn.execute("SELECT id FROM wall").fetchone()[0]
    climber_id = upsert_climber(conn, "Niklavs")
    video_id = upsert_video(
        conn,
        Video(None, "/raw/x.mov", "/norm/x.mp4", "sha-x", 30.0, 1280, 720, 30.0, "ok", None),
    )
    route_id = upsert_route(
        conn,
        Route(id=None, wall_id=wall_id, origin=RouteSource.MANUAL),
    )
    upsert_attempt(
        conn,
        Attempt(
            id=None, video_id=video_id, climber_id=climber_id, route_id=route_id,
            start_frame=0, end_frame=100, time_seconds=3.3,
            send=True, attempts_count=1,
            route_source=RouteSource.MANUAL, config_hash="cfg-1",
        ),
    )
    # Try to flip the manual route_source to auto — the TRIGGER must abort.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE attempt SET route_source = 'auto' WHERE route_id = ?", (route_id,)
        )


def test_leaderboard_orders_sends_first():
    conn = _mem()
    conn.execute("INSERT INTO wall(gym_name) VALUES ('K')")
    wall_id = conn.execute("SELECT id FROM wall").fetchone()[0]
    erik = upsert_climber(conn, "Erik")
    emil = upsert_climber(conn, "Emil")
    video_id = upsert_video(
        conn,
        Video(None, "/raw/x.mov", "/norm/x.mp4", "sha-x", 30.0, 1280, 720, 30.0, "ok", None),
    )
    route_id = upsert_route(conn, Route(id=None, wall_id=wall_id, origin=RouteSource.MANUAL))
    for climber_id, start, end, t, send in [
        (erik, 0, 100, 5.0, True),
        (emil, 200, 350, 4.0, False),
        (emil, 400, 550, 3.0, True),
    ]:
        upsert_attempt(
            conn,
            Attempt(
                id=None, video_id=video_id, climber_id=climber_id, route_id=route_id,
                start_frame=start, end_frame=end, time_seconds=t,
                send=send, attempts_count=1,
                route_source=RouteSource.MANUAL, config_hash="cfg",
            ),
        )
    rows = leaderboard(conn, route_id)
    # Sends first (Emil 3.0, Erik 5.0), then fails (Emil 4.0).
    assert [r["climber_name"] for r in rows] == ["Emil", "Erik", "Emil"]
    assert rows[0]["send"] == 1
    assert rows[0]["time_seconds"] == 3.0
