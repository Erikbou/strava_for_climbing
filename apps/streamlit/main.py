"""Artemis dashboard — Strava-style feed, post detail, profile.

Single-page app; view selection lives in `st.query_params["view"]` so links
are refresh-safe and shareable. Visual language matches the landing page
at https://artemis.spcf.app/ (lowercase wordmark, amber-orange gradient,
SF Pro Rounded, pill-shaped CTAs).
"""

from __future__ import annotations

import streamlit as st
import views  # streamlit puts the script dir on sys.path

st.set_page_config(
    page_title="artemis — sports technology",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      :root {
        --orange-1: #ffb84a;
        --orange-2: #ff9a1f;
        --orange-3: #f47a00;
        --orange-deep: #e36a00;
        --orange-shadow: rgba(228, 106, 0, 0.35);
        --ink: #111;
        --ink-soft: #1a1a1a;
        --muted: #6B6B6F;
        --placeholder: #b5b5b5;
        --field-border: #d5d5d5;
        --hairline: #ECECEC;
        --bg: #FFFFFF;
        --bg-soft: #FAFAFA;
      }

      /* ---------- Reset Streamlit chrome ---------- */
      [data-testid="stHeader"], [data-testid="stToolbar"],
      footer, #MainMenu { display: none !important; }
      [data-testid="stSidebar"] { display: none !important; }
      .block-container {
        padding-top: 1rem; padding-bottom: 5rem;
        max-width: 720px;
      }
      html, body, [class*="stApp"] {
        background: var(--bg-soft);
        color: var(--ink);
        font-family: -apple-system, "SF Pro Rounded", "SF Pro Text",
                     "Helvetica Neue", Helvetica, Arial, system-ui, sans-serif;
        font-weight: 600;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
      }
      h1, h2, h3, h4, p, span, div { letter-spacing: -0.005em; }

      /* ---------- Activity cards ---------- */
      .activity-card {
        background: var(--bg);
        border: 1px solid var(--hairline);
        border-radius: 16px;
        padding: 0;
        margin-bottom: 18px;
        overflow: hidden;
        box-shadow: 0 1px 2px rgba(17, 17, 17, 0.03);
      }
      .activity-head { display: flex; align-items: center; padding: 16px 18px 12px 18px; }
      .activity-head .meta { flex: 1; min-width: 0; }
      .activity-head .name {
        font-weight: 800; font-size: 15px; color: var(--ink);
        letter-spacing: -0.01em;
      }
      .activity-head .time { font-size: 12px; color: var(--muted); font-weight: 600; }
      .activity-title {
        padding: 0 18px 12px 18px;
        font-size: 19px; font-weight: 800; color: var(--ink);
        line-height: 1.25; letter-spacing: -0.015em;
      }

      /* ---------- Avatar ---------- */
      .avatar {
        width: 42px; height: 42px; border-radius: 50%;
        background: linear-gradient(180deg, var(--orange-1) 0%, var(--orange-2) 60%, var(--orange-3) 100%);
        color: white;
        display: flex; align-items: center; justify-content: center;
        font-weight: 800; font-size: 14px; letter-spacing: 0.3px;
        margin-right: 12px; flex-shrink: 0;
        box-shadow: 0 2px 6px var(--orange-shadow);
      }
      .avatar.lg { width: 68px; height: 68px; font-size: 22px; }

      /* ---------- Badges ---------- */
      .badge {
        display: inline-block; padding: 4px 12px; border-radius: 999px;
        font-size: 11px; font-weight: 800; letter-spacing: 0.5px;
        text-transform: lowercase;
      }
      .badge-send {
        color: white;
        background: linear-gradient(180deg, var(--orange-1) 0%, var(--orange-2) 45%, var(--orange-3) 100%);
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.5),
          inset 0 -1px 0 rgba(160,70,0,0.18),
          0 2px 4px var(--orange-shadow);
      }
      .badge-attempt {
        background: #F1F1F2; color: var(--ink-soft);
      }
      .badge-color {
        display: inline-flex; align-items: center; gap: 8px;
        padding: 3px 12px 3px 7px; border-radius: 999px;
        font-size: 12px; font-weight: 700;
        background: #F4F4F5; color: var(--ink);
        text-transform: lowercase;
      }
      .badge-color .swatch {
        width: 12px; height: 12px; border-radius: 50%;
        display: inline-block;
        box-shadow: inset 0 0 0 1px rgba(0,0,0,0.08);
      }

      /* ---------- Stat tiles ---------- */
      .stat-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0;
        border-top: 1px solid var(--hairline);
        background: #FAFAFA;
      }
      .stat-row .tile {
        padding: 14px 12px; text-align: left;
        border-right: 1px solid var(--hairline);
      }
      .stat-row .tile:last-child { border-right: none; }
      .stat-row .tile .value {
        font-size: 22px; font-weight: 800; color: var(--ink);
        line-height: 1.1; letter-spacing: -0.02em;
      }
      .stat-row .tile .label {
        font-size: 10px; color: var(--muted); text-transform: lowercase;
        letter-spacing: 0.6px; margin-top: 4px; font-weight: 700;
      }

      .stat-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1px;
        background: var(--hairline);
        border: 1px solid var(--hairline);
        border-radius: 16px;
        overflow: hidden;
        margin: 12px 0 24px 0;
      }
      .stat-grid .tile { background: var(--bg); padding: 18px; }
      .stat-grid .tile .value {
        font-size: 28px; font-weight: 800; color: var(--ink);
        line-height: 1.05; letter-spacing: -0.025em;
      }
      .stat-grid .tile .label {
        font-size: 10px; color: var(--muted); text-transform: lowercase;
        letter-spacing: 0.6px; margin-top: 6px; font-weight: 700;
      }

      /* ---------- Section headings ---------- */
      .section-h {
        font-size: 11px; color: var(--muted); text-transform: lowercase;
        letter-spacing: 0.8px; font-weight: 800;
        margin: 28px 0 10px 0;
      }

      /* ---------- Buttons (Streamlit) ---------- */
      .stButton > button {
        border-radius: 999px !important;
        font-weight: 700 !important;
        padding: 8px 22px !important;
        font-size: 14px !important;
        letter-spacing: -0.005em !important;
        border: 1.5px solid var(--field-border) !important;
        background: var(--bg) !important;
        color: var(--ink) !important;
        transition: filter 120ms ease, transform 80ms ease !important;
      }
      .stButton > button:hover {
        filter: brightness(0.97);
        border-color: #c5c5c5 !important;
      }
      .stButton > button[kind="primary"] {
        color: #FFFFFF !important;
        background: linear-gradient(180deg,
          var(--orange-1) 0%, var(--orange-2) 45%, var(--orange-3) 100%) !important;
        border: none !important;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.55),
          inset 0 -2px 0 rgba(160,70,0,0.18),
          0 4px 10px var(--orange-shadow),
          0 2px 4px rgba(0,0,0,0.05) !important;
        text-shadow: 0 1px 0 rgba(160,70,0,0.18);
      }
      .stButton > button[kind="primary"]:hover {
        filter: brightness(1.04);
        transform: none;
      }
      .stButton > button[kind="primary"]:active {
        transform: translateY(1px);
      }

      /* ---------- Inputs ---------- */
      .stTextInput input, .stSelectbox > div > div,
      [data-testid="stFileUploader"] section {
        border-radius: 14px !important;
        border-color: var(--field-border) !important;
      }
      .stTextInput input { font-weight: 600 !important; color: var(--ink) !important; }

      /* ---------- Video player ---------- */
      video { border-radius: 12px; background: #000; }

      /* ---------- Profile header ---------- */
      .profile-head {
        display: flex; align-items: center; gap: 18px;
        padding: 14px 0 22px 0;
        border-bottom: 1px solid var(--hairline);
        margin-bottom: 22px;
      }
      .profile-head .name {
        font-size: 26px; font-weight: 800; color: var(--ink);
        letter-spacing: -0.025em;
      }
      .profile-head .sub { font-size: 13px; color: var(--muted); font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _brand_bar() -> None:
    view = st.query_params.get("view", "feed")
    cols = st.columns([3, 1, 1])
    with cols[0]:
        st.markdown(
            """
            <div style="padding-top: 12px; padding-bottom: 4px;">
              <span style="font-weight: 800; font-size: 32px;
                           letter-spacing: -0.025em; color: var(--orange-2);
                           line-height: 1;">
                artemis<sup style="font-size:0.4em;font-weight:700;
                                   vertical-align:super;line-height:0;
                                   color:var(--orange-3);">&trade;</sup>
              </span>
              <div style="font-size: 10px; color: var(--muted);
                          text-transform: lowercase; letter-spacing: 1.6px;
                          font-weight: 800; margin-top: 4px;">
                strava for climbing
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.write("")
        if st.button(
            "home",
            key="brand-home",
            type="secondary",
            use_container_width=True,
        ):
            st.query_params.clear()
            st.query_params["view"] = "feed"
            st.rerun()
    with cols[2]:
        st.write("")
        if view != "upload" and st.button(
            "+ upload",
            key="brand-upload",
            type="primary",
            use_container_width=True,
        ):
            st.query_params.clear()
            st.query_params["view"] = "upload"
            st.rerun()
    st.markdown(
        "<div style='border-bottom:1px solid var(--hairline); "
        "margin: 10px 0 26px 0;'></div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    _brand_bar()
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
