"""Cached query layer. All Streamlit pages call helpers from here — never the
Supabase client directly from a page. ``@st.cache_data`` prevents the leaderboard
query from re-running on every interaction.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from strava_climbing import db


@st.cache_data(ttl=60)
def routes() -> list[dict[str, Any]]:
    return db.list_routes(db.connect())


@st.cache_data(ttl=60)
def leaderboard(route_id: int) -> list[dict[str, Any]]:
    return db.leaderboard(db.connect(), route_id)


@st.cache_data(ttl=60)
def attempt(attempt_id: int) -> dict[str, Any] | None:
    return db.get_attempt_detail(db.connect(), attempt_id)


@st.cache_data(ttl=60)
def route_meta(route_id: int) -> dict[str, Any] | None:
    return db.get_route_with_wall(db.connect(), route_id)
