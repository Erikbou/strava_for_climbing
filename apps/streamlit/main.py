"""Strava-for-climbing dashboard — Strava-style feed, post detail, profile.

Single-page app; view selection lives in `st.query_params["view"]` so links
are refresh-safe and shareable. Light theme + Strava orange is configured in
`.streamlit/config.toml`.
"""

from __future__ import annotations

import streamlit as st
import views  # streamlit puts the script dir on sys.path

st.set_page_config(
    page_title="Artemis — Strava for Climbing",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      /* ---------- Reset Streamlit chrome ---------- */
      [data-testid="stHeader"], [data-testid="stToolbar"],
      footer, #MainMenu { display: none !important; }
      [data-testid="stSidebar"] { display: none !important; }
      .block-container {
        padding-top: 1rem; padding-bottom: 5rem;
        max-width: 720px;
      }
      html, body, [class*="stApp"] {
        background: #FAFAFA;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                     Oxygen, "Helvetica Neue", Arial, sans-serif;
      }

      /* ---------- Brand bar ---------- */
      .brand-bar {
        display: flex; align-items: baseline; justify-content: space-between;
        padding: 12px 0 18px 0;
        border-bottom: 1px solid #ECECEC;
        margin-bottom: 24px;
      }
      .brand-bar .wordmark {
        font-weight: 900; font-size: 26px; letter-spacing: -0.5px;
        color: #1F2328; line-height: 1;
      }
      .brand-bar .wordmark .accent { color: #FC4C02; }
      .brand-bar .tagline {
        font-size: 11px; color: #8A8F98; text-transform: uppercase;
        letter-spacing: 1.5px; font-weight: 700; margin-left: 12px;
      }

      /* ---------- Activity cards ---------- */
      .activity-card {
        background: #FFFFFF;
        border: 1px solid #E5E5E5;
        border-radius: 8px;
        padding: 0;
        margin-bottom: 16px;
        overflow: hidden;
      }
      .activity-head { display: flex; align-items: center; padding: 14px 16px 12px 16px; }
      .activity-head .meta { flex: 1; min-width: 0; }
      .activity-head .name { font-weight: 700; font-size: 15px; color: #1F2328; }
      .activity-head .time { font-size: 12px; color: #8A8F98; }
      .activity-title {
        padding: 0 16px 12px 16px;
        font-size: 18px; font-weight: 700; color: #1F2328;
        line-height: 1.25;
      }

      /* ---------- Avatar circle ---------- */
      .avatar {
        width: 40px; height: 40px; border-radius: 50%;
        background: #FC4C02; color: white;
        display: flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 14px; letter-spacing: 0.5px;
        margin-right: 12px; flex-shrink: 0;
      }
      .avatar.lg { width: 64px; height: 64px; font-size: 22px; }

      /* ---------- Badges ---------- */
      .badge {
        display: inline-block; padding: 3px 10px; border-radius: 999px;
        font-size: 11px; font-weight: 700; letter-spacing: 0.3px;
        text-transform: uppercase;
      }
      .badge-send { background: #FC4C02; color: white; }
      .badge-attempt { background: #ECECEC; color: #555; }
      .badge-color {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 2px 10px 2px 6px; border-radius: 999px;
        font-size: 12px; font-weight: 600;
        background: #F1F1F2; color: #1F2328;
      }
      .badge-color .swatch {
        width: 12px; height: 12px; border-radius: 50%;
        display: inline-block; border: 1px solid rgba(0,0,0,0.08);
      }

      /* ---------- Stat tiles ---------- */
      .stat-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0;
        border-top: 1px solid #ECECEC;
      }
      .stat-row .tile {
        padding: 14px 12px; text-align: left;
        border-right: 1px solid #ECECEC;
      }
      .stat-row .tile:last-child { border-right: none; }
      .stat-row .tile .value {
        font-size: 22px; font-weight: 800; color: #1F2328; line-height: 1.1;
      }
      .stat-row .tile .label {
        font-size: 11px; color: #8A8F98; text-transform: uppercase;
        letter-spacing: 0.5px; margin-top: 4px;
      }

      .stat-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 1px;
        background: #ECECEC;
        border: 1px solid #ECECEC;
        border-radius: 8px;
        overflow: hidden;
        margin: 12px 0 20px 0;
      }
      .stat-grid .tile {
        background: #FFFFFF; padding: 16px;
      }
      .stat-grid .tile .value {
        font-size: 26px; font-weight: 800; color: #1F2328; line-height: 1.1;
      }
      .stat-grid .tile .label {
        font-size: 11px; color: #8A8F98; text-transform: uppercase;
        letter-spacing: 0.5px; margin-top: 4px;
      }

      /* ---------- Section headings ---------- */
      .section-h {
        font-size: 11px; color: #8A8F98; text-transform: uppercase;
        letter-spacing: 0.8px; font-weight: 700;
        margin: 24px 0 8px 0;
      }

      /* ---------- Buttons ---------- */
      .stButton > button {
        border-radius: 999px !important;
        font-weight: 600 !important;
        padding: 6px 18px !important;
      }
      .stButton > button[kind="primary"] {
        background: #FC4C02 !important; border-color: #FC4C02 !important;
        color: white !important;
      }
      .stButton > button[kind="primary"]:hover {
        background: #E04400 !important; border-color: #E04400 !important;
      }
      .stButton > button[kind="secondary"] {
        background: #FFFFFF !important; color: #1F2328 !important;
        border: 1px solid #D5D5D5 !important;
      }

      /* ---------- Video player ---------- */
      video { border-radius: 8px; background: #000; }

      /* ---------- Profile header ---------- */
      .profile-head {
        display: flex; align-items: center; gap: 16px;
        padding: 12px 0 20px 0;
        border-bottom: 1px solid #ECECEC;
        margin-bottom: 20px;
      }
      .profile-head .name { font-size: 24px; font-weight: 800; color: #1F2328; }
      .profile-head .sub { font-size: 13px; color: #8A8F98; }
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
            <div style="padding-top: 10px; padding-bottom: 4px;">
              <span style="font-weight: 900; font-size: 28px; letter-spacing: -0.6px;
                           color: #1F2328; line-height: 1;">
                Artemis<span style="color:#FC4C02;">.</span>
              </span>
              <div style="font-size: 10px; color: #8A8F98; text-transform: uppercase;
                          letter-spacing: 1.8px; font-weight: 700; margin-top: 4px;">
                Strava for Climbing
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.write("")
        if st.button("Home", key="brand-home", type="secondary", use_container_width=True):
            st.query_params.clear()
            st.query_params["view"] = "feed"
            st.rerun()
    with cols[2]:
        st.write("")
        if view != "upload" and st.button(
            "+ Upload", key="brand-upload", type="primary", use_container_width=True
        ):
            st.query_params.clear()
            st.query_params["view"] = "upload"
            st.rerun()
    st.markdown(
        "<div style='border-bottom:1px solid #ECECEC; margin: 8px 0 24px 0;'></div>",
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
