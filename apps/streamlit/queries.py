"""Cached read layer for the dashboard. All Streamlit pages call helpers from
here — never open a connection from a page.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from strava_climbing.config import runtime as R
from strava_climbing.db import connect, init_db


def _ensure_schema_once() -> None:
    if st.session_state.get("_db_initialized"):
        return
    init_db()
    st.session_state["_db_initialized"] = True


@st.cache_data(ttl=30)
def feed(limit: int = 50) -> list[dict[str, Any]]:
    """Reverse-chronological list of recent attempts, joined with climber and route."""
    _ensure_schema_once()
    with connect(read_only=R.is_demo_mode()) as conn:
        rows = conn.execute(
            """
            SELECT a.id            AS attempt_id,
                   a.title         AS title,
                   a.time_seconds  AS time_seconds,
                   a.smoothness_pct AS smoothness_pct,
                   a.dynamic_moves AS dynamic_moves,
                   a.longest_reach_px AS longest_reach_px,
                   a.hang_time_seconds AS hang_time_seconds,
                   a.idle_seconds  AS idle_seconds,
                   a.send          AS send,
                   a.overlay_path  AS overlay_path,
                   a.highlight_path AS highlight_path,
                   a.posted_at     AS posted_at,
                   c.id            AS climber_id,
                   c.name          AS climber_name,
                   r.id            AS route_id,
                   r.color         AS route_color,
                   w.gym_name      AS gym_name
              FROM attempt a
              LEFT JOIN climber c ON c.id = a.climber_id
              LEFT JOIN route   r ON r.id = a.route_id
              LEFT JOIN wall    w ON w.id = r.wall_id
             ORDER BY a.posted_at DESC, a.id DESC
             LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


@st.cache_data(ttl=30)
def attempt(attempt_id: int) -> dict[str, Any] | None:
    _ensure_schema_once()
    with connect(read_only=R.is_demo_mode()) as conn:
        row = conn.execute(
            """
            SELECT a.*, c.name AS climber_name, c.id AS climber_id,
                   r.id AS route_id, r.color AS route_color,
                   w.gym_name AS gym_name, v.normalized_path AS normalized_path
              FROM attempt a
              LEFT JOIN climber c ON c.id = a.climber_id
              LEFT JOIN route   r ON r.id = a.route_id
              LEFT JOIN wall    w ON w.id = r.wall_id
              LEFT JOIN video   v ON v.id = a.video_id
             WHERE a.id = %s
            """,
            (attempt_id,),
        ).fetchone()
    return dict(row) if row else None


@st.cache_data(ttl=30)
def climber(climber_id: int) -> dict[str, Any] | None:
    _ensure_schema_once()
    with connect(read_only=R.is_demo_mode()) as conn:
        row = conn.execute(
            """
            SELECT c.id, c.name,
                   COUNT(a.id)                                       AS attempts_logged,
                   COUNT(*) FILTER (WHERE a.send IS TRUE)            AS sends,
                   MIN(a.time_seconds) FILTER (WHERE a.send IS TRUE) AS fastest_send_seconds
              FROM climber c
              LEFT JOIN attempt a ON a.climber_id = c.id
             WHERE c.id = %s
             GROUP BY c.id, c.name
            """,
            (climber_id,),
        ).fetchone()
    return dict(row) if row else None


@st.cache_data(ttl=30)
def climber_attempts(climber_id: int, limit: int = 20) -> list[dict[str, Any]]:
    _ensure_schema_once()
    with connect(read_only=R.is_demo_mode()) as conn:
        rows = conn.execute(
            """
            SELECT a.id            AS attempt_id,
                   a.time_seconds  AS time_seconds,
                   a.send          AS send,
                   a.posted_at     AS posted_at,
                   r.color         AS route_color,
                   w.gym_name      AS gym_name
              FROM attempt a
              LEFT JOIN route r ON r.id = a.route_id
              LEFT JOIN wall  w ON w.id = r.wall_id
             WHERE a.climber_id = %s
             ORDER BY a.posted_at DESC, a.id DESC
             LIMIT %s
            """,
            (climber_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]
