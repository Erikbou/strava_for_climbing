"""Artemis dashboard — single-page feed, post detail, profile.

View selection lives in `st.query_params["view"]` so links are refresh-safe
and shareable. Visual language matches the landing page at
https://artemis.spcf.app/ (lowercase wordmark, amber-orange gradient,
SF Pro Rounded, pill-shaped CTAs). Layout patterns borrowed from Strava
(see docs/plans/2026-05-28-artemis-ui-strava-layout.md).
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st
import views  # streamlit puts the script dir on sys.path

_IMG_DIR = Path(__file__).resolve().parents[2] / "src" / "strava_climbing" / "img"
_LOGO_ICON = _IMG_DIR / "logo.png"
_LOGOTYPE = _IMG_DIR / "artemis-logotype.png"


def _data_uri(path: Path) -> str:
    """Read a PNG and return a `data:image/png;base64,...` URI for inline `<img src>`."""
    return f"data:image/png;base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


_LOGOTYPE_URI = _data_uri(_LOGOTYPE) if _LOGOTYPE.exists() else ""


st.set_page_config(
    page_title="artemis — sports technology",
    page_icon=str(_LOGO_ICON) if _LOGO_ICON.exists() else None,
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
        --muted-2: #8E8E93;
        --placeholder: #b5b5b5;
        --field-border: #d5d5d5;
        --hairline: #ECECEC;
        --bg: #FFFFFF;
        --bg-soft: #FAFAFA;

        /* Spacing scale (8px base) */
        --s-1: 4px;
        --s-2: 8px;
        --s-3: 12px;
        --s-4: 16px;
        --s-5: 20px;
        --s-6: 24px;
        --s-7: 32px;
        --s-8: 40px;

        /* Card paddings — collapse on small screens */
        --card-pad-x: clamp(14px, 4vw, 20px);
        --card-pad-y: clamp(12px, 3vw, 16px);
      }

      /* ---------- Reset Streamlit chrome ---------- */
      [data-testid="stHeader"], [data-testid="stToolbar"],
      footer, #MainMenu { display: none !important; }
      [data-testid="stSidebar"] { display: none !important; }
      .block-container {
        padding-top: var(--s-3);
        padding-bottom: var(--s-8);
        padding-left: clamp(12px, 4vw, 24px);
        padding-right: clamp(12px, 4vw, 24px);
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
      h1, h2, h3, h4 { line-height: 1.2; letter-spacing: -0.015em; }
      p, span, div { letter-spacing: -0.005em; line-height: 1.45; }

      /* Tabular numbers in every stat tile so digits align vertically. */
      .stat-row .tile .value,
      .stat-grid .tile .value,
      [data-testid="stMetricValue"] {
        font-variant-numeric: tabular-nums;
        font-feature-settings: "tnum" 1;
      }

      /* ---------- Streamlit containers become activity cards ---------- */
      [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--bg) !important;
        border: 1px solid var(--hairline) !important;
        border-radius: 18px !important;
        margin-bottom: var(--s-3) !important;
        padding: 0 !important;
        box-shadow: 0 1px 2px rgba(17,17,17,0.03);
        overflow: hidden;
      }
      [data-testid="stVerticalBlockBorderWrapper"] > div > div {
        padding: 0 !important;
        gap: 0 !important;
      }

      /* Section markup that sits inside a card */
      .card-head {
        display: flex; align-items: center;
        padding: var(--card-pad-y) var(--card-pad-x) var(--s-3);
      }
      .card-head .meta { flex: 1; min-width: 0; }
      .card-head .name {
        font-weight: 800; font-size: 15px; color: var(--ink);
        letter-spacing: -0.01em;
      }
      .card-head .sub { font-size: 12px; color: var(--muted); font-weight: 600; }

      .card-title {
        padding: 0 var(--card-pad-x) var(--s-2);
        font-size: clamp(17px, 4.2vw, 19px); font-weight: 800;
        color: var(--ink); line-height: 1.25; letter-spacing: -0.015em;
      }
      .card-chips {
        padding: 0 var(--card-pad-x) var(--s-3);
        display: flex; gap: var(--s-2); flex-wrap: wrap; align-items: center;
      }

      /* Streamlit-rendered video sits flush inside the card */
      [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVideo"] video,
      [data-testid="stVerticalBlockBorderWrapper"] video {
        border-radius: 0 !important;
        display: block;
        width: 100%;
        background: #000;
      }
      [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVideo"] {
        margin: 0 !important;
      }

      /* ---------- Avatar ---------- */
      .avatar {
        width: 40px; height: 40px; border-radius: 50%;
        background: linear-gradient(180deg, var(--orange-1) 0%, var(--orange-2) 60%, var(--orange-3) 100%);
        color: white;
        display: flex; align-items: center; justify-content: center;
        font-weight: 800; font-size: 14px; letter-spacing: 0.3px;
        margin-right: var(--s-3); flex-shrink: 0;
        box-shadow: 0 2px 6px var(--orange-shadow);
      }
      .avatar.lg { width: 64px; height: 64px; font-size: 22px; }

      /* ---------- Badges ---------- */
      .badge {
        display: inline-block; padding: 4px 12px; border-radius: 999px;
        font-size: 11px; font-weight: 800; letter-spacing: 0.5px;
        text-transform: lowercase;
        line-height: 1.4;
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
        background: var(--bg-soft);
      }
      .stat-row .tile {
        padding: var(--s-3) var(--s-3); text-align: left;
        border-right: 1px solid var(--hairline);
      }
      .stat-row .tile:last-child { border-right: none; }
      .stat-row .tile .value {
        font-size: clamp(20px, 5vw, 24px); font-weight: 800; color: var(--ink);
        line-height: 1.05; letter-spacing: -0.025em;
      }
      .stat-row .tile .label {
        font-size: 10px; color: var(--muted); text-transform: lowercase;
        letter-spacing: 0.6px; margin-top: 4px; font-weight: 800;
      }

      /* Collapse 1x4 -> 2x2 on small screens */
      @media (max-width: 480px) {
        .stat-row { grid-template-columns: repeat(2, 1fr); }
        .stat-row .tile {
          border-right: 1px solid var(--hairline);
          border-bottom: 1px solid var(--hairline);
        }
        .stat-row .tile:nth-child(2n) { border-right: none; }
        .stat-row .tile:nth-last-child(-n+2) { border-bottom: none; }
      }

      /* 2x3 grid on the post detail */
      .stat-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1px;
        background: var(--hairline);
        border: 1px solid var(--hairline);
        border-radius: 16px;
        overflow: hidden;
        margin: var(--s-3) 0 var(--s-6);
      }
      .stat-grid .tile { background: var(--bg); padding: 18px; }
      .stat-grid .tile .value {
        font-size: clamp(22px, 6vw, 28px); font-weight: 800; color: var(--ink);
        line-height: 1.05; letter-spacing: -0.025em;
      }
      .stat-grid .tile .label {
        font-size: 10px; color: var(--muted); text-transform: lowercase;
        letter-spacing: 0.6px; margin-top: 6px; font-weight: 800;
      }
      @media (max-width: 480px) {
        .stat-grid { grid-template-columns: repeat(2, 1fr); }
      }

      /* ---------- Hairline section header ---------- */
      .section-h {
        display: flex; align-items: center; gap: var(--s-3);
        font-size: 11px; color: var(--muted); text-transform: lowercase;
        letter-spacing: 0.8px; font-weight: 800;
        margin: var(--s-7) 0 var(--s-3);
      }
      .section-h::after {
        content: ""; flex: 1; height: 1px; background: var(--hairline);
      }

      /* ---------- CTA / action row beneath the card ---------- */
      .card-cta-pad { padding: var(--s-3) var(--card-pad-x); }

      /* ---------- Buttons (Streamlit) ---------- */
      .stButton > button {
        border-radius: 999px !important;
        font-weight: 700 !important;
        padding: 8px 18px !important;
        font-size: 13px !important;
        letter-spacing: -0.005em !important;
        border: 1.5px solid var(--field-border) !important;
        background: var(--bg) !important;
        color: var(--ink) !important;
        transition: filter 120ms ease, transform 80ms ease !important;
        white-space: nowrap !important;
        min-height: 40px !important;
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
        min-height: 44px !important;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.55),
          inset 0 -2px 0 rgba(160,70,0,0.18),
          0 4px 10px var(--orange-shadow),
          0 2px 4px rgba(0,0,0,0.05) !important;
        text-shadow: 0 1px 0 rgba(160,70,0,0.18);
      }
      .stButton > button[kind="primary"]:hover {
        filter: brightness(1.04);
      }
      .stButton > button[kind="primary"]:active {
        transform: translateY(1px);
      }
      .stButton > button:focus-visible {
        outline: 3px solid rgba(244, 122, 0, 0.4) !important;
        outline-offset: 3px !important;
      }

      /* ---------- Inputs ---------- */
      .stTextInput input, .stSelectbox > div > div,
      [data-testid="stFileUploader"] section {
        border-radius: 14px !important;
        border-color: var(--field-border) !important;
      }
      .stTextInput input {
        font-weight: 600 !important;
        color: var(--ink) !important;
      }
      .stTextInput input:focus,
      .stSelectbox > div > div:focus-within {
        border-color: var(--orange-3) !important;
        box-shadow: 0 0 0 3px rgba(244, 122, 0, 0.18) !important;
      }

      /* ---------- Profile header ---------- */
      .profile-head {
        display: flex; align-items: center; gap: var(--s-4);
        padding: var(--s-3) 0 var(--s-5);
        border-bottom: 1px solid var(--hairline);
        margin-bottom: var(--s-5);
      }
      .profile-head .name {
        font-size: clamp(22px, 6vw, 28px); font-weight: 800; color: var(--ink);
        letter-spacing: -0.025em; line-height: 1.1;
      }
      .profile-head .sub { font-size: 13px; color: var(--muted); font-weight: 600; }

      /* ---------- Brand bar ---------- */
      .brand-row {
        position: sticky; top: 0; z-index: 100;
        background: rgba(250, 250, 250, 0.85);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        margin: 0 calc(-1 * clamp(12px, 4vw, 24px)) var(--s-5);
        padding: var(--s-3) clamp(12px, 4vw, 24px);
        border-bottom: 1px solid var(--hairline);
      }

      /* ---------- Active nav state ---------- */
      .nav-active .stButton > button {
        background: linear-gradient(180deg,
          rgba(255,184,74,0.10) 0%, rgba(255,154,31,0.10) 100%) !important;
        border-color: rgba(255,154,31,0.45) !important;
        color: var(--orange-3) !important;
      }

      /* ---------- Lighter back-link button ---------- */
      .back-link .stButton > button {
        background: transparent !important;
        border: none !important;
        color: var(--muted) !important;
        font-weight: 700 !important;
        padding: 6px 0 !important;
        min-height: 32px !important;
        text-align: left !important;
        justify-content: flex-start !important;
      }
      .back-link .stButton > button:hover {
        color: var(--ink) !important;
        filter: none;
        border: none !important;
      }

      /* ---------- Form density ---------- */
      [data-testid="stForm"] {
        background: var(--bg) !important;
        border: 1px solid var(--hairline) !important;
        border-radius: 18px !important;
        padding: var(--s-4) var(--card-pad-x) !important;
      }
      .stTextInput, .stSelectbox, [data-testid="stFileUploader"] {
        margin-bottom: var(--s-3) !important;
      }
      .stTextInput label, .stSelectbox label,
      [data-testid="stFileUploader"] label {
        font-size: 11px !important;
        font-weight: 800 !important;
        letter-spacing: 0.4px;
        text-transform: lowercase;
        color: var(--muted) !important;
      }

      /* ---------- Reduced motion ---------- */
      @media (prefers-reduced-motion: reduce) {
        .stButton > button,
        .stButton > button[kind="primary"]:active {
          transition: none !important;
          transform: none !important;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def _brand_bar() -> None:
    view = st.query_params.get("view", "feed")
    cols = st.columns([3, 1, 1])
    with cols[0]:
        if _LOGOTYPE_URI:
            st.markdown(
                f"""
                <div role="banner" style="padding-top: 6px; padding-bottom: 2px;">
                  <img src="{_LOGOTYPE_URI}" alt="artemis"
                       style="height: clamp(34px, 9vw, 44px); width: auto;
                              display: block; margin-bottom: 4px;" />
                  <div style="font-size: 10px; color: var(--muted);
                              text-transform: lowercase; letter-spacing: 1.6px;
                              font-weight: 800;">
                    sports technology
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div role="banner" style="padding-top: 8px; padding-bottom: 4px;">
                  <div style="font-weight: 800; font-size: 30px;
                              letter-spacing: -0.025em; color: var(--orange-2);
                              line-height: 1;">
                    artemis
                  </div>
                  <div style="font-size: 10px; color: var(--muted);
                              text-transform: lowercase; letter-spacing: 1.6px;
                              font-weight: 800; margin-top: 4px;">
                    sports technology
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with cols[1]:
        st.write("")
        if view == "feed":
            st.markdown("<div class='nav-active'>", unsafe_allow_html=True)
        if st.button(
            "home",
            key="brand-home",
            type="secondary",
            use_container_width=True,
        ):
            st.query_params.clear()
            st.query_params["view"] = "feed"
            st.rerun()
        if view == "feed":
            st.markdown("</div>", unsafe_allow_html=True)
    with cols[2]:
        st.write("")
        # On the upload view the CTA becomes a "you are here" pill — secondary
        # styling with the nav-active highlight; off-upload it's the full
        # gradient primary CTA so the call-to-action still pops.
        if view == "upload":
            st.markdown("<div class='nav-active'>", unsafe_allow_html=True)
            if st.button(
                "uploading",
                key="brand-upload-here",
                type="secondary",
                use_container_width=True,
                disabled=True,
            ):
                pass
            st.markdown("</div>", unsafe_allow_html=True)
        elif st.button(
            "+ upload",
            key="brand-upload",
            type="primary",
            use_container_width=True,
        ):
            st.query_params.clear()
            st.query_params["view"] = "upload"
            st.rerun()


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
