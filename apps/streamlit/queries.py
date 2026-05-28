"""Cached read layer for the dashboard. All Streamlit pages call helpers from
here — never open a connection from a page.
"""

from __future__ import annotations

from typing import Any

import psycopg
import streamlit as st

from strava_climbing.config import runtime as R
from strava_climbing.db import connect, init_db

# Module-level flag so the schema is migrated once per Python process, not
# once per browser session. (st.session_state.persists across runOnSave
# reruns, which means a fresh ALTER/CREATE in SCHEMA_SQL would never apply
# until the user manually cleared their session — too easy a foot-gun.)
_SCHEMA_INITIALIZED = False


def _ensure_schema_once(*, force: bool = False) -> None:
    global _SCHEMA_INITIALIZED
    if _SCHEMA_INITIALIZED and not force:
        return
    init_db()
    _SCHEMA_INITIALIZED = True


def _retry_after_migrate(fn):
    """If a query fails with ``UndefinedTable``/``UndefinedColumn`` (i.e. the
    in-process schema flag is stale because someone added DDL on this branch),
    force a re-migration and retry once. Keeps the page from crashing on the
    first request after a schema bump."""
    try:
        return fn()
    except (psycopg.errors.UndefinedTable, psycopg.errors.UndefinedColumn):
        _ensure_schema_once(force=True)
        return fn()


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


@st.cache_data(ttl=15)
def kudos_counts(attempt_ids: tuple[int, ...]) -> dict[int, int]:
    """Return ``{attempt_id: like_count}`` for the given ids. Empty input
    short-circuits without a query."""
    _ensure_schema_once()
    if not attempt_ids:
        return {}

    def _run() -> dict[int, int]:
        with connect(read_only=R.is_demo_mode()) as conn:
            rows = conn.execute(
                """
                SELECT attempt_id, COUNT(*) AS n
                  FROM kudos
                 WHERE attempt_id = ANY(%s)
                 GROUP BY attempt_id
                """,
                (list(attempt_ids),),
            ).fetchall()
        counts = {aid: 0 for aid in attempt_ids}
        for r in rows:
            counts[r["attempt_id"]] = int(r["n"])
        return counts

    return _retry_after_migrate(_run)


@st.cache_data(ttl=15)
def my_kudos(attempt_ids: tuple[int, ...], session_id: str) -> set[int]:
    """Return the subset of ``attempt_ids`` the given session has already liked."""
    _ensure_schema_once()
    if not attempt_ids or not session_id:
        return set()

    def _run() -> set[int]:
        with connect(read_only=R.is_demo_mode()) as conn:
            rows = conn.execute(
                """
                SELECT attempt_id FROM kudos
                 WHERE session_id = %s AND attempt_id = ANY(%s)
                """,
                (session_id, list(attempt_ids)),
            ).fetchall()
        return {int(r["attempt_id"]) for r in rows}

    return _retry_after_migrate(_run)


def toggle_kudos(attempt_id: int, session_id: str) -> int:
    """Insert or delete one kudo for ``(attempt_id, session_id)`` and return
    the new total like count. Bypasses read-only mode — likes are the one
    write demo users get."""
    _ensure_schema_once()

    def _run() -> int:
        with connect() as conn:
            existing = conn.execute(
                "SELECT 1 FROM kudos WHERE attempt_id = %s AND session_id = %s",
                (attempt_id, session_id),
            ).fetchone()
            if existing:
                conn.execute(
                    "DELETE FROM kudos WHERE attempt_id = %s AND session_id = %s",
                    (attempt_id, session_id),
                )
            else:
                conn.execute(
                    "INSERT INTO kudos(attempt_id, session_id) VALUES (%s, %s)"
                    " ON CONFLICT DO NOTHING",
                    (attempt_id, session_id),
                )
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM kudos WHERE attempt_id = %s",
                (attempt_id,),
            ).fetchone()
        return int(row["n"])

    n = _retry_after_migrate(_run)
    # Invalidate the cached count + per-session list so the UI updates.
    kudos_counts.clear()
    my_kudos.clear()
    return n


@st.cache_data(ttl=30)
def climbers(limit: int = 50) -> list[dict[str, Any]]:
    """Directory of every climber + their headline stats. Used by the profile
    picker when no specific climber is selected."""
    _ensure_schema_once()
    with connect(read_only=R.is_demo_mode()) as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.name,
                   COUNT(a.id)                                       AS attempts_logged,
                   COUNT(*) FILTER (WHERE a.send IS TRUE)            AS sends,
                   MIN(a.time_seconds) FILTER (WHERE a.send IS TRUE) AS fastest_send_seconds,
                   MAX(a.posted_at)                                   AS last_seen
              FROM climber c
              LEFT JOIN attempt a ON a.climber_id = c.id
             GROUP BY c.id, c.name
             ORDER BY sends DESC NULLS LAST, attempts_logged DESC NULLS LAST,
                      c.name ASC
             LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


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
