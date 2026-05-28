"""Artemis views: feed, post detail, profile, upload.

Single-page app. View selection lives in ``st.query_params["view"]``. All
data access goes through ``queries`` so caching and read-only mode are
honoured uniformly. The visual chrome (cards, stat tiles, avatars, badges)
is composed from HTML fragments emitted via ``st.markdown(...,
unsafe_allow_html=True)`` because Streamlit's primitives can't quite hit
the density and hierarchy we want.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import queries
import streamlit as st

from strava_climbing import orchestrate
from strava_climbing.config import gym as G
from strava_climbing.config import paths as P

ARTEMIS_ORANGE = "#ff9a1f"

# Stable palette for color swatches in badges (matches CSS rules in main.py).
_COLOR_SWATCHES = {
    "white": "#F5F5F5", "yellow": "#F5C400", "orange": "#ff9a1f",
    "green": "#2EA44F", "blue": "#1F6FEB", "red": "#D7263D",
    "purple": "#7C3AED", "black": "#111", "pink": "#EC4899",
}


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------

def go(view: str, **params: Any) -> None:
    """Set the current view + params and rerun. Refresh-safe URLs."""
    st.query_params.clear()
    st.query_params["view"] = view
    for k, v in params.items():
        st.query_params[k] = str(v)
    st.rerun()


def back_button(label: str = "Back to feed") -> None:
    if st.button(label, key=f"back-{label}", type="secondary"):
        go("feed")


# ---------------------------------------------------------------------------
# HTML fragment builders
# ---------------------------------------------------------------------------

def _initials(name: str | None) -> str:
    if not name:
        return "?"
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _avatar(name: str | None, *, size: str = "") -> str:
    cls = "avatar" + (f" {size}" if size else "")
    return f'<div class="{cls}">{_initials(name)}</div>'


def _color_badge(color: str | None) -> str:
    if not color:
        return '<span class="badge-color"><span class="swatch" style="background:#ccc"></span>untagged</span>'
    swatch = _COLOR_SWATCHES.get(color.lower(), "#888")
    return (
        f'<span class="badge-color">'
        f'<span class="swatch" style="background:{swatch}"></span>{color}'
        f'</span>'
    )


def _send_badge(send: bool) -> str:
    cls = "badge badge-send" if send else "badge badge-attempt"
    text = "Send" if send else "Attempt"
    return f'<span class="{cls}">{text}</span>'


def _grade_for(color: str | None, gym: str = G.DEFAULT_GYM) -> str:
    g = G.lookup(color, gym=gym)
    return g["grade"] if g else "—"


def _grade_label(color: str | None, gym: str = G.DEFAULT_GYM) -> str | None:
    g = G.lookup(color, gym=gym)
    return g["label"] if g else None


def _activity_title(row: dict[str, Any]) -> str:
    """Activity title generated from the climb metadata."""
    grade = _grade_for(row.get("route_color"))
    verb = "Sent" if row["send"] else "Attempted"
    if row.get("route_color"):
        return f"{verb} {row['route_color'].title()} · {grade}"
    return f"{verb} a climb"


def _format_age(posted_at: Any) -> str:
    if not isinstance(posted_at, datetime):
        return ""
    delta = datetime.now(posted_at.tzinfo) - posted_at
    secs = int(delta.total_seconds())
    if secs < 60:
        return "Just now"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def _stat_value(v: Any, *, fmt: str = "{:g}", default: str = "—") -> str:
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return fmt.format(v)
    return str(v)


def _stat_tile(label: str, value: str) -> str:
    return (
        f'<div class="tile">'
        f'<div class="value">{value}</div>'
        f'<div class="label">{label}</div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def feed_view() -> None:
    st.markdown(
        "<div class='section-h'>Following · recent climbs</div>",
        unsafe_allow_html=True,
    )

    rows = queries.feed()
    if not rows:
        st.info(
            "Your feed is empty. Tap **+ Upload** in the top bar to drop in a "
            "30-90 s bouldering clip — we'll detect pose, time the send, "
            "score smoothness, and cut a highlight."
        )
        return

    for r in rows:
        _feed_card(r)


def _feed_card(r: dict[str, Any]) -> None:
    climber = r.get("climber_name") or "Unknown climber"
    gym = r.get("gym_name") or "Unknown gym"
    age = _format_age(r.get("posted_at"))
    title = _activity_title(r)

    st.markdown(
        f"""
        <div class="activity-card">
          <div class="activity-head">
            {_avatar(climber)}
            <div class="meta">
              <div class="name">{climber}</div>
              <div class="time">{age} · {gym}</div>
            </div>
            <div>{_send_badge(bool(r['send']))}</div>
          </div>
          <div class="activity-title">{title}</div>
          <div style="padding: 0 16px 12px 16px;">
            {_color_badge(r.get("route_color"))}
          </div>
          <div class="stat-row">
            {_stat_tile("Time", _stat_value(r.get("time_seconds"), fmt="{:.1f}s"))}
            {_stat_tile("Dynamic", _stat_value(r.get("dynamic_moves"), fmt="{:d}"))}
            {_stat_tile("Smoothness", _stat_value(r.get("smoothness_pct"), fmt="{:.0f}"))}
            {_stat_tile("Hang", _stat_value(r.get("hang_time_seconds"), fmt="{:.1f}s"))}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Streamlit-native action row beneath the card (HTML buttons can't trigger
    # reruns, and st.button can't live inside the HTML fragment).
    cta = st.columns([2, 2, 4])
    with cta[0]:
        if st.button(
            "view",
            key=f"view-{r['attempt_id']}",
            type="primary",
            use_container_width=True,
        ):
            go("post", attempt_id=r["attempt_id"])
    with cta[1]:
        cid = r.get("climber_id")
        if cid is not None and st.button(
            "profile",
            key=f"prof-{r['attempt_id']}",
            use_container_width=True,
        ):
            go("profile", climber_id=cid)


def post_view(attempt_id: int) -> None:
    a = queries.attempt(attempt_id)
    if a is None:
        st.error(f"Post not found (attempt {attempt_id}).")
        back_button()
        return

    back_button()

    climber = a.get("climber_name") or "Unknown climber"
    gym = a.get("gym_name") or "Unknown gym"
    age = _format_age(a.get("posted_at"))
    color = a.get("route_color")
    grade = _grade_for(color)
    grade_label = _grade_label(color) or ""
    title = _activity_title(a)

    header_style = (
        "padding: 0 0 16px 0; border-bottom: 1px solid #ECECEC; "
        "margin-bottom: 16px;"
    )
    title_style = (
        "margin: 0 0 6px 0; font-size: 28px; font-weight: 800; color: #111;"
    )
    st.markdown(
        f"""
        <div class="activity-head" style="{header_style}">
          {_avatar(climber, size="lg")}
          <div class="meta">
            <div style="font-size:20px;font-weight:800;color:#111;">{climber}</div>
            <div style="font-size:13px;color:#6B6B6F;">{age} · {gym}</div>
          </div>
          <div>{_send_badge(bool(a['send']))}</div>
        </div>
        <h1 style="{title_style}">{title}</h1>
        <div style="margin-bottom: 8px;">
          {_color_badge(color)} &nbsp;
          <span style="font-size:20px;font-weight:800;color:#ff9a1f;">{grade}</span>
          <span style="color:#6B6B6F;font-size:13px;">· {grade_label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Highlight clip first — most visceral piece of the post.
    highlight = a.get("highlight_path")
    if highlight and Path(highlight).exists():
        st.markdown("<div class='section-h'>Highlight</div>", unsafe_allow_html=True)
        with open(highlight, "rb") as f:
            st.video(f, format="video/mp4")

    # Stat grid.
    st.markdown("<div class='section-h'>Stats</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="stat-grid">
          {_stat_tile("Time to top", _stat_value(a.get("time_seconds"), fmt="{:.1f}s"))}
          {_stat_tile("Smoothness", _stat_value(a.get("smoothness_pct"), fmt="{:.0f}"))}
          {_stat_tile("Dynamic moves", _stat_value(a.get("dynamic_moves"), fmt="{:d}"))}
          {_stat_tile("Longest reach", _stat_value(a.get("longest_reach_px"), fmt="{:.0f} px"))}
          {_stat_tile("Hang on hardest", _stat_value(a.get("hang_time_seconds"), fmt="{:.1f}s"))}
          {_stat_tile("Idle / rest", _stat_value(a.get("idle_seconds"), fmt="{:.1f}s"))}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Full skeleton overlay further down — secondary in the visual hierarchy.
    overlay = a.get("overlay_path")
    if overlay and Path(overlay).exists():
        st.markdown("<div class='section-h'>Full climb · skeleton overlay</div>", unsafe_allow_html=True)
        with open(overlay, "rb") as f:
            st.video(f, format="video/mp4")
    else:
        st.caption("Skeleton overlay not available for this attempt.")


def profile_view(climber_id: int) -> None:
    c = queries.climber(climber_id)
    if c is None:
        st.error(f"Climber not found (id {climber_id}).")
        back_button()
        return

    back_button()

    fastest = c.get("fastest_send_seconds")
    name = c["name"]
    st.markdown(
        f"""
        <div class="profile-head">
          {_avatar(name, size="lg")}
          <div>
            <div class="name">{name}</div>
            <div class="sub">Climber profile</div>
          </div>
        </div>
        <div class="stat-grid" style="grid-template-columns: repeat(3, 1fr);">
          {_stat_tile("Sends", _stat_value(c.get("sends"), fmt="{:d}", default="0"))}
          {_stat_tile("Attempts", _stat_value(c.get("attempts_logged"), fmt="{:d}", default="0"))}
          {_stat_tile("Fastest send", _stat_value(fastest, fmt="{:.1f}s"))}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='section-h'>Recent climbs</div>", unsafe_allow_html=True)
    rows = queries.climber_attempts(climber_id)
    if not rows:
        st.caption("No climbs logged yet.")
        return

    for r in rows:
        color = r.get("route_color")
        gym = r.get("gym_name") or "Unknown gym"
        age = _format_age(r.get("posted_at"))
        st.markdown(
            f"""
            <div class="activity-card" style="margin-bottom: 10px;">
              <div style="padding: 12px 16px;">
                <div style="display:flex;align-items:center;gap:12px;">
                  <div style="flex:1;min-width:0;">
                    {_color_badge(color)}
                    &nbsp; <strong style="color:#111;">{_grade_for(color)}</strong>
                    &nbsp; {_send_badge(bool(r['send']))}
                    <div style="color:#6B6B6F;font-size:12px;margin-top:6px;">
                      {age} · {gym} · {r['time_seconds']:.1f}s
                    </div>
                  </div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "open post",
            key=f"open-{r['attempt_id']}",
            type="secondary",
            use_container_width=True,
        ):
            go("post", attempt_id=r["attempt_id"])


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def upload_view() -> None:
    back_button()
    st.markdown(
        """
        <h1 style="font-size:28px;font-weight:800;color:#111;margin:8px 0 4px 0;">
          Upload a climb
        </h1>
        <p style="color:#6B6B6F;font-size:14px;margin:0 0 18px 0;">
          30-90 second portrait clip works best. We'll detect pose, time the
          send, score smoothness, and cut a highlight.
        </p>
        """,
        unsafe_allow_html=True,
    )

    with st.form("upload-form", clear_on_submit=False):
        uploaded = st.file_uploader(
            "Climbing video",
            type=["mp4", "mov", "m4v", "mkv", "webm"],
            accept_multiple_files=False,
            help="Mobile-shot clips up to ~60 s work best.",
        )
        cols = st.columns(2)
        with cols[0]:
            climber_name = st.text_input(
                "Climber name", placeholder="e.g. Niklavs Visockis"
            )
            color_choices = list(G.COLOR_GRADES[G.DEFAULT_GYM].keys())
            color = st.selectbox(
                "Hold color (drives the grade)",
                options=color_choices,
                index=0,
            )
        with cols[1]:
            gym = st.text_input("Gym", value=G.DEFAULT_GYM)
            grade_preview = G.lookup(color, gym=gym)
            if grade_preview:
                st.markdown(
                    f"""
                    <div style="padding:10px 0;">
                      <div style="color:#6B6B6F;font-size:11px;text-transform:uppercase;
                                  letter-spacing:0.5px;font-weight:700;">
                        Inferred grade
                      </div>
                      <div style="font-size:24px;font-weight:800;color:#ff9a1f;">
                        {grade_preview['grade']}
                      </div>
                      <div style="color:#6B6B6F;font-size:13px;">{grade_preview['label']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Grade lookup only configured for Klättercentret Akalla in v1.")

        submitted = st.form_submit_button(
            "Analyze climb", type="primary", use_container_width=True
        )

    if not submitted:
        return
    if uploaded is None:
        st.error("Pick a video file first.")
        return
    if not climber_name.strip():
        st.error("Climber name is required.")
        return
    size_mb = uploaded.size / (1024 * 1024)
    if size_mb > 25:
        st.warning(
            f"Your file is {size_mb:.0f} MB — large clips are usually >2 min "
            "and the tracker fragments. v1 works best on **30-90 second** clips "
            "of one attempt. Continuing anyway."
        )

    attempt_id = _run_upload_pipeline(uploaded, climber_name.strip(), color, gym.strip())
    if attempt_id is None:
        st.warning(
            "Processing finished but no climber track was found. Common causes:\n\n"
            "- **Clip too long** (>90 s): the tracker fragments across many short "
            "tracks; none has enough continuous presence to register as an attempt.\n"
            "- **Climber goes in and out of frame** between camera moves.\n"
            "- **Multiple people in the foreground** confuse the tracker.\n\n"
            "Try a 30-90 s clip of a single attempt where the climber stays mostly "
            "in frame."
        )
        return

    queries.feed.clear()
    queries.attempt.clear()
    queries.climber.clear()
    queries.climber_attempts.clear()
    go("post", attempt_id=attempt_id)


def _run_upload_pipeline(uploaded: Any, climber_name: str, color: str, gym: str) -> int | None:
    P.ensure_dirs()
    raw_bytes = uploaded.getbuffer()
    sha = hashlib.sha256(raw_bytes).hexdigest()
    suffix = Path(uploaded.name).suffix.lower() or ".mp4"
    raw_path = P.RAW_DIR / f"{sha[:12]}{suffix}"
    raw_path.write_bytes(raw_bytes)

    with st.spinner(
        "Normalizing video, running pose detection, deriving stats, "
        "rendering overlay and highlight..."
    ):
        return orchestrate.process_uploaded_file(
            raw_path,
            climber_name=climber_name,
            color=color,
            gym=gym,
        )
