"""Strava-for-climbing dashboard — Strava-style feed, post detail, profile.

Single-page app; view selection lives in `st.query_params["view"]` so links
are refresh-safe and shareable. Light theme + Strava orange is configured in
`.streamlit/config.toml`.
"""

from __future__ import annotations

import streamlit as st
import views  # streamlit puts the script dir on sys.path

st.set_page_config(
    page_title="Strava for Climbing",
    page_icon="🧗",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      /* Tighten cards and hide the default header. */
      [data-testid="stHeader"] { background: transparent; }
      [data-testid="stMetricLabel"] { color: #666 !important; font-size: 12px; }
      div[data-testid="stMetricValue"] { color: #1F2328; font-weight: 700; }
      .block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 760px; }
      .stButton > button[kind="primary"] {
        background: #FC4C02 !important; border-color: #FC4C02 !important;
      }
      .stButton > button[kind="primary"]:hover {
        background: #E04400 !important; border-color: #E04400 !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def main() -> None:
    view = st.query_params.get("view", "feed")

    if view == "post":
        try:
            attempt_id = int(st.query_params.get("attempt_id", "0"))
        except (TypeError, ValueError):
            attempt_id = 0
        views.post_view(attempt_id)
        return

    if view == "profile":
        try:
            climber_id = int(st.query_params.get("climber_id", "0"))
        except (TypeError, ValueError):
            climber_id = 0
        views.profile_view(climber_id)
        return

    if view == "upload":
        views.upload_view()
        return

    views.feed_view()


if __name__ == "__main__":
    main()
