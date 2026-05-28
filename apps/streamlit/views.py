"""Render functions for the three Strava-style views: feed, post, profile.

Single-page app. View selection lives in ``st.session_state["view"]`` /
``st.query_params``. All read access goes through ``queries`` so caching and
read-only mode are honoured uniformly.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import queries
import streamlit as st

from strava_climbing.config import gym as G

STRAVA_ORANGE = "#FC4C02"

# --- view router helpers ----------------------------------------------------


def go(view: str, **params: Any) -> None:
    """Set the current view and re-run. Query params keep refresh-safe URLs."""
    st.query_params["view"] = view
    for k, v in params.items():
        st.query_params[k] = str(v)
    st.rerun()


def back_button(label: str = "← Back to feed") -> None:
    if st.button(label, type="secondary"):
        go("feed")


# --- shared formatting ------------------------------------------------------


def _grade_for(color: str | None) -> str:
    g = G.lookup(color)
    return g["grade"] if g else "—"


def _grade_label_for(color: str | None) -> str | None:
    g = G.lookup(color)
    return g["label"] if g else None


def _format_age(posted_at: Any) -> str:
    if not isinstance(posted_at, datetime):
        return ""
    delta = datetime.now(posted_at.tzinfo) - posted_at
    secs = int(delta.total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def _colored_badge(color: str | None) -> str:
    if not color:
        return "<span style='color:#888'>untagged</span>"
    swatch = {
        "white": "#F5F5F5", "yellow": "#F5C400", "orange": "#FC4C02",
        "green": "#2EA44F", "blue": "#1F6FEB", "red": "#D7263D",
        "purple": "#7C3AED", "black": "#1F2328", "pink": "#EC4899",
    }.get(color.lower(), "#888")
    text = "#1F2328" if color.lower() in {"white", "yellow", "pink"} else "#FFFFFF"
    return (
        f"<span style='background:{swatch};color:{text};padding:2px 10px;"
        f"border-radius:999px;font-size:12px;font-weight:600'>{color}</span>"
    )


def _send_badge(send: bool) -> str:
    if send:
        return (
            f"<span style='background:{STRAVA_ORANGE};color:#fff;padding:2px 10px;"
            f"border-radius:999px;font-size:12px;font-weight:700'>SEND</span>"
        )
    return (
        "<span style='background:#E5E5E5;color:#555;padding:2px 10px;"
        "border-radius:999px;font-size:12px;font-weight:600'>ATTEMPT</span>"
    )


# --- views ------------------------------------------------------------------


def feed_view() -> None:
    st.markdown(
        f"<h1 style='color:{STRAVA_ORANGE};margin-bottom:0'>Strava for Climbing</h1>"
        "<p style='color:#666;margin-top:4px'>Feed · recent climbs by everyone</p>",
        unsafe_allow_html=True,
    )

    rows = queries.feed()
    if not rows:
        st.info(
            "No climbs yet. Run `uv run strava process` after dropping videos in `data/raw/`, "
            "or run `python scripts/seed_demo.py` to populate demo data."
        )
        return

    for r in rows:
        _feed_card(r)


def _feed_card(r: dict[str, Any]) -> None:
    with st.container(border=True):
        # Header row
        top = st.columns([3, 1])
        with top[0]:
            climber = r.get("climber_name") or "Unknown climber"
            gym = r.get("gym_name") or "Unknown gym"
            posted = _format_age(r.get("posted_at"))
            st.markdown(
                f"**{climber}** · {gym}  \n"
                f"<span style='color:#888;font-size:12px'>{posted}</span>",
                unsafe_allow_html=True,
            )
        with top[1]:
            st.markdown(
                f"<div style='text-align:right'>{_send_badge(r['send'])}</div>",
                unsafe_allow_html=True,
            )

        # Grade + color line
        color = r.get("route_color")
        grade = _grade_for(color)
        st.markdown(
            f"{_colored_badge(color)} &nbsp; "
            f"<span style='font-size:18px;font-weight:700'>{grade}</span>",
            unsafe_allow_html=True,
        )

        # Stats row
        m = st.columns(4)
        m[0].metric("Time", f"{r['time_seconds']:.1f}s")
        m[1].metric("Dynamic moves", r.get("dynamic_moves") if r.get("dynamic_moves") is not None else "—")
        m[2].metric(
            "Smoothness",
            f"{r['smoothness_pct']:.0f}" if r.get("smoothness_pct") is not None else "—",
        )
        m[3].metric(
            "Hang time",
            f"{r['hang_time_seconds']:.1f}s" if r.get("hang_time_seconds") else "—",
        )

        # CTA row
        cta = st.columns([1, 1, 3])
        with cta[0]:
            if st.button("View post", key=f"view-{r['attempt_id']}", type="primary"):
                go("post", attempt_id=r["attempt_id"])
        with cta[1]:
            cid = r.get("climber_id")
            if cid is not None and st.button("Profile", key=f"prof-{r['attempt_id']}"):
                go("profile", climber_id=cid)


def post_view(attempt_id: int) -> None:
    a = queries.attempt(attempt_id)
    if a is None:
        st.error(f"Post not found (attempt {attempt_id}).")
        back_button()
        return

    back_button()

    # Title block
    climber = a.get("climber_name") or "Unknown climber"
    gym = a.get("gym_name") or "Unknown gym"
    posted = _format_age(a.get("posted_at"))
    st.markdown(
        f"<h2 style='margin-bottom:0'>{climber}'s climb at {gym}</h2>"
        f"<div style='color:#888'>{posted}</div>",
        unsafe_allow_html=True,
    )

    color = a.get("route_color")
    grade_info = G.lookup(color) or {}
    grade = grade_info.get("grade", "—")
    label = grade_info.get("label", "")
    st.markdown(
        f"{_colored_badge(color)} &nbsp; "
        f"<span style='font-size:22px;font-weight:700'>{grade}</span> "
        f"<span style='color:#888'>· {label}</span> &nbsp; {_send_badge(bool(a['send']))}",
        unsafe_allow_html=True,
    )
    st.divider()

    # Stats grid
    st.subheader("Climb stats")
    grid = st.columns(4)
    grid[0].metric("Time to top", f"{a['time_seconds']:.1f}s")
    grid[1].metric(
        "Dynamic moves",
        a.get("dynamic_moves") if a.get("dynamic_moves") is not None else "—",
    )
    grid[2].metric(
        "Longest reach",
        f"{a['longest_reach_px']:.0f}px" if a.get("longest_reach_px") else "—",
    )
    grid[3].metric(
        "Hang on hardest move",
        f"{a['hang_time_seconds']:.1f}s" if a.get("hang_time_seconds") else "—",
    )

    grid2 = st.columns(4)
    grid2[0].metric(
        "Smoothness",
        f"{a['smoothness_pct']:.0f}" if a.get("smoothness_pct") is not None else "—",
    )
    grid2[1].metric(
        "Idle/rest",
        f"{a['idle_seconds']:.1f}s" if a.get("idle_seconds") else "—",
    )

    # Highlight clip
    st.divider()
    st.subheader("Highlight")
    highlight = a.get("highlight_path")
    if highlight and Path(highlight).exists():
        with open(highlight, "rb") as f:
            st.video(f, format="video/mp4")
    else:
        st.caption("Highlight clip not available yet — run the pipeline to generate.")

    # Full overlay
    st.subheader("Full climb · skeleton overlay")
    overlay = a.get("overlay_path")
    if overlay and Path(overlay).exists():
        with open(overlay, "rb") as f:
            st.video(f, format="video/mp4")
    else:
        st.caption(
            "Overlay not available. The annotated video lives at "
            f"`{overlay}` once the pipeline writes it."
        )


def profile_view(climber_id: int) -> None:
    c = queries.climber(climber_id)
    if c is None:
        st.error(f"Climber not found (id {climber_id}).")
        back_button()
        return

    back_button()

    st.markdown(
        f"<h2 style='margin-bottom:0'>{c['name']}</h2>"
        f"<div style='color:#888'>Climber profile</div>",
        unsafe_allow_html=True,
    )

    st.divider()
    cols = st.columns(3)
    cols[0].metric("Sends", c.get("sends") or 0)
    cols[1].metric("Attempts logged", c.get("attempts_logged") or 0)
    fastest = c.get("fastest_send_seconds")
    cols[2].metric("Fastest send", f"{fastest:.1f}s" if fastest is not None else "—")

    st.divider()
    st.subheader("Recent climbs")
    rows = queries.climber_attempts(climber_id)
    if not rows:
        st.caption("No climbs logged for this climber yet.")
        return
    for r in rows:
        with st.container(border=True):
            line = st.columns([4, 1])
            with line[0]:
                color = r.get("route_color")
                gym = r.get("gym_name") or "Unknown gym"
                st.markdown(
                    f"{_colored_badge(color)} &nbsp; **{_grade_for(color)}** "
                    f"<span style='color:#888'>· {gym}</span> &nbsp; "
                    f"{_send_badge(bool(r['send']))}  \n"
                    f"<span style='color:#888;font-size:12px'>"
                    f"{_format_age(r.get('posted_at'))} · {r['time_seconds']:.1f}s</span>",
                    unsafe_allow_html=True,
                )
            with line[1]:
                if st.button("Open", key=f"open-{r['attempt_id']}"):
                    go("post", attempt_id=r["attempt_id"])
