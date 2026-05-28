"""Strava-for-climbing dashboard. Single-page; selects a route, shows the
leaderboard, optionally lets two attempts be compared side-by-side.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from strava_climbing.config import runtime as R

from . import queries

st.set_page_config(
    page_title="Strava for Climbing",
    page_icon="🧗",
    layout="wide",
)


def _empty_state():
    st.title("Strava for Climbing 🧗")
    st.info(
        "No processed attempts yet. Run:\n\n"
        "```bash\n"
        "uv run strava ingest      # normalize videos in data/raw/\n"
        "uv run strava process     # pose + metrics + overlays\n"
        "```\n\n"
        "Then refresh this page."
    )


def main() -> None:
    routes = queries.routes()
    if not routes:
        _empty_state()
        return

    st.title("Strava for Climbing 🧗")
    if R.is_demo_mode():
        st.caption("Demo mode — frozen database, uploads disabled.")

    routes_with_attempts = [r for r in routes if r["attempt_count"] > 0]
    if not routes_with_attempts:
        st.warning("Routes exist but no attempts have been recorded yet.")
        return

    labels = {
        r["id"]: f"{r['color'] or '—'} · {r['attempt_count']} attempts ({r['origin']})"
        for r in routes_with_attempts
    }
    sel = st.sidebar.radio(
        "Route", options=list(labels.keys()), format_func=lambda rid: labels[rid]
    )
    _render_route(sel)


def _render_route(route_id: int) -> None:
    meta = queries.route_meta(route_id)
    if not meta:
        st.error(f"route {route_id} not found")
        return

    title = f"Route {meta['id']}"
    if meta.get("color"):
        title += f" · {meta['color']}"
    if meta.get("gym_name"):
        title += f" · {meta['gym_name']}"
    st.header(title)
    if meta.get("origin") == "auto":
        st.caption(f"Auto-clustered (confidence: {meta.get('cluster_confidence', 0):.2f})")

    rows = queries.leaderboard(route_id)
    if not rows:
        st.warning("No attempts on this route yet.")
        return

    _leaderboard_table(rows)

    st.divider()
    _attempt_picker(rows)


def _leaderboard_table(rows: list[dict]) -> None:
    st.subheader("Leaderboard")
    # Order is already (send DESC, time ASC) thanks to the composite index in db.py.
    display = []
    for i, r in enumerate(rows, start=1):
        display.append({
            "#": i,
            "Climber": r.get("climber_name") or "—",
            "Time (s)": f"{r['time_seconds']:.1f}",
            "Smoothness": f"{r['smoothness_pct']:.0f}" if r.get("smoothness_pct") is not None else "—",
            "Send?": "✅" if r["send"] else "—",
            "Attempts in clip": r["attempts_count"],
        })
    st.dataframe(display, use_container_width=True, hide_index=True)


def _attempt_picker(rows: list[dict]) -> None:
    options = {
        r["attempt_id"]: f"#{i+1} · {r.get('climber_name') or '—'} · {r['time_seconds']:.1f}s"
        + (" · SEND" if r["send"] else "")
        for i, r in enumerate(rows)
    }
    cols = st.columns([2, 2, 1])
    with cols[0]:
        a_id = st.selectbox("Attempt A", options=list(options.keys()),
                             format_func=lambda x: options[x], key="a_pick")
    with cols[1]:
        b_id = st.selectbox(
            "Attempt B (optional)",
            options=[None, *list(options.keys())],
            format_func=lambda x: "— none —" if x is None else options[x],
            key="b_pick",
        )
    with cols[2]:
        st.write("")
        st.write("")
        compare = st.checkbox("Side-by-side", value=False)

    if compare and b_id is not None:
        cols = st.columns(2)
        with cols[0]:
            _render_attempt(a_id, title="Attempt A")
        with cols[1]:
            _render_attempt(b_id, title="Attempt B")
    else:
        _render_attempt(a_id, title="Selected attempt")


def _render_attempt(attempt_id: int, *, title: str) -> None:
    a = queries.attempt(attempt_id)
    if a is None:
        st.warning(f"{title}: attempt not found")
        return
    st.markdown(f"**{title}** — {a.get('climber_name') or '—'}")
    overlay_key = a.get("overlay_path")
    if overlay_key:
        src = queries.overlay_playback_source(overlay_key)
        if isinstance(src, Path):
            if src.exists():
                with open(src, "rb") as f:
                    st.video(f, format="video/mp4")
            else:
                st.warning("Overlay missing locally — re-run `strava process`.")
        else:
            st.video(src, format="video/mp4")
    else:
        st.warning(
            "Overlay missing — Streamlit cannot run inference live. "
            "Re-run `strava process` to regenerate."
        )
        normalized_key = a.get("normalized_path")
        if normalized_key:
            src = queries.normalized_playback_source(normalized_key)
            if isinstance(src, Path):
                if src.exists():
                    with open(src, "rb") as f:
                        st.video(f, format="video/mp4")
            else:
                st.video(src, format="video/mp4")

    metrics_cols = st.columns(3)
    metrics_cols[0].metric("Time", f"{a['time_seconds']:.1f}s")
    if a.get("smoothness_pct") is not None:
        metrics_cols[1].metric("Smoothness", f"{a['smoothness_pct']:.0f}")
    else:
        metrics_cols[1].metric("Smoothness", "—")
    metrics_cols[2].metric("Result", "SEND ✅" if a["send"] else "fall")


if __name__ == "__main__":
    main()
