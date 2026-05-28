"""Cached query layer. All Streamlit pages call helpers from here — never
the backend directly from a page. ``@st.cache_data`` prevents the leaderboard
query from re-running on every interaction.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from strava_climbing import db


@st.cache_data(ttl=60)
def routes() -> list[dict[str, Any]]:
    db.init_db()
    return db.list_routes()


@st.cache_data(ttl=60)
def leaderboard(route_id: int) -> list[dict[str, Any]]:
    return db.leaderboard(route_id)


@st.cache_data(ttl=60)
def attempt(attempt_id: int) -> dict[str, Any] | None:
    return db.get_attempt_detail(attempt_id)


@st.cache_data(ttl=60)
def route_meta(route_id: int) -> dict[str, Any] | None:
    return db.get_route_with_wall(route_id)


def overlay_playback_source(key: str):
    """URL (Supabase) or local Path (SQLite) ready for ``st.video()``."""
    return db.overlay_playback_source(key)


def normalized_playback_source(key: str):
    return db.normalized_playback_source(key)
