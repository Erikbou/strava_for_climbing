"""Cached query layer. All Streamlit pages call helpers from here — never
``sqlite3.connect()`` from a page. ``@st.cache_data`` prevents the leaderboard
query from re-running on every interaction.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from strava_climbing.config import paths as P
from strava_climbing.config import runtime as R
from strava_climbing.db import connect, init_db
from strava_climbing.db import leaderboard as _leaderboard
from strava_climbing.db import list_routes as _list_routes


def _db_path():
    if R.is_demo_mode() and P.DEMO_DB_PATH.exists():
        return P.DEMO_DB_PATH
    if not P.DB_PATH.exists():
        # First-time Streamlit launch with no pipeline run yet — make the
        # empty-state path work cleanly instead of OperationalError on missing tables.
        init_db(P.DB_PATH)
    return P.DB_PATH


@st.cache_data(ttl=60)
def routes() -> list[dict[str, Any]]:
    with connect(_db_path(), read_only=R.is_demo_mode()) as conn:
        return _list_routes(conn)


@st.cache_data(ttl=60)
def leaderboard(route_id: int) -> list[dict[str, Any]]:
    with connect(_db_path(), read_only=R.is_demo_mode()) as conn:
        return _leaderboard(conn, route_id)


@st.cache_data(ttl=60)
def attempt(attempt_id: int) -> dict[str, Any] | None:
    with connect(_db_path(), read_only=R.is_demo_mode()) as conn:
        row = conn.execute(
            """
            SELECT a.*, c.name AS climber_name, r.color AS route_color,
                   w.gym_name AS gym_name, v.normalized_path AS normalized_path
              FROM attempt a
              LEFT JOIN climber c ON c.id = a.climber_id
              LEFT JOIN route   r ON r.id = a.route_id
              LEFT JOIN wall    w ON w.id = r.wall_id
              LEFT JOIN video   v ON v.id = a.video_id
             WHERE a.id = ?
            """,
            (attempt_id,),
        ).fetchone()
    return dict(row) if row else None


@st.cache_data(ttl=60)
def route_meta(route_id: int) -> dict[str, Any] | None:
    with connect(_db_path(), read_only=R.is_demo_mode()) as conn:
        row = conn.execute(
            "SELECT r.*, w.gym_name "
            "FROM route r JOIN wall w ON w.id = r.wall_id "
            "WHERE r.id = ?",
            (route_id,),
        ).fetchone()
    return dict(row) if row else None
