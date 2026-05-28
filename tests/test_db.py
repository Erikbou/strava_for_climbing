"""Schema + trigger integration tests against a Postgres instance.

Requires ``DATABASE_URL`` (set automatically by ``specific dev``/``specific exec``).
Tests are skipped if no DB is available.
"""

from __future__ import annotations

import os

import pytest

psycopg = pytest.importorskip("psycopg")

from strava_climbing.db import (  # noqa: E402
    SCHEMA_SQL,
    connect,
    leaderboard,
    upsert_attempt,
    upsert_climber,
    upsert_route,
    upsert_video,
)
from strava_climbing.provenance import RouteSource  # noqa: E402
from strava_climbing.schema import Attempt, Route, Video  # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set (run inside `specific dev` / `specific exec`)",
)

# Names of every persistent object created by SCHEMA_SQL — used to wipe between tests.
_TABLES = ("attempt", "hold", "route", "wall", "video", "climber")


@pytest.fixture
def conn():
    """Open a connection, apply schema, truncate before AND after each test.

    Post-test truncation matters because the test DB is currently shared with
    the dev Postgres — leaving rows behind would clobber the running app.
    """
    c = connect()
    c.execute(SCHEMA_SQL)
    truncate = f"TRUNCATE TABLE {', '.join(_TABLES)} RESTART IDENTITY CASCADE"
    c.execute(truncate)
    try:
        yield c
    finally:
        try:
            c.execute(truncate)
        finally:
            c.close()


def test_schema_creates_cleanly(conn):
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = ANY(%s)",
        (list(_TABLES),),
    ).fetchall()
    names = {r["table_name"] for r in rows}
    assert names == set(_TABLES)


def test_upsert_climber_idempotent(conn):
    a = upsert_climber(conn, "Erik")
    b = upsert_climber(conn, "Erik")
    assert a == b


def test_video_dedup_by_source_sha256(conn):
    v1 = Video(None, "/raw/a.mov", "/norm/a.mp4", "sha-abc", 30.0, 1280, 720, 30.0, "ok", None)
    id1 = upsert_video(conn, v1)
    v2 = Video(None, "/raw/b.mov", "/norm/b.mp4", "sha-abc", 30.0, 1280, 720, 30.0, "ok", None)
    id2 = upsert_video(conn, v2)
    assert id1 == id2


def test_manual_route_trigger_blocks_overwrite(conn):
    wall_id = conn.execute(
        "INSERT INTO wall(gym_name) VALUES ('Klättercentret') RETURNING id"
    ).fetchone()["id"]
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
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute(
            "UPDATE attempt SET route_source = 'auto' WHERE route_id = %s", (route_id,)
        )


def test_leaderboard_orders_sends_first(conn):
    wall_id = conn.execute(
        "INSERT INTO wall(gym_name) VALUES ('K') RETURNING id"
    ).fetchone()["id"]
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
    assert [r["climber_name"] for r in rows] == ["Emil", "Erik", "Emil"]
    assert rows[0]["send"] is True
    assert rows[0]["time_seconds"] == 3.0
