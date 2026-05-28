"""Artemis views: feed, post detail, profile, upload, leaderboards.

Single-page app. View selection lives in ``st.query_params["view"]``. The
visual chrome (cards, stat tiles, avatars, pills, glass overlays, marble
colour chips) is composed from HTML fragments emitted via
``st.markdown(..., unsafe_allow_html=True)`` because Streamlit's primitives
can't match the Artemis Aqua spec on their own.

Feed exposes two modes via ``?mode=cards|list``:
- ``cards`` (default): Strava-style hero cards.
- ``list``: dense Hacker-News-style ranked list of every climb.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import queries
import streamlit as st

from strava_climbing import orchestrate, titles
from strava_climbing.config import gym as G
from strava_climbing.config import paths as P

# ---------------------------------------------------------------------------
# Tokens that need to live in Python (kept parallel to main.py CSS tokens)
# ---------------------------------------------------------------------------

_COLOR_SWATCHES = {
    "white":  "#F0EFEC", "yellow": "#F0C400", "orange": "#FF9A1F",
    "green":  "#2EA44F", "blue":   "#1F6FEB", "red":    "#D7263D",
    "purple": "#7C3AED", "black":  "#1A1A1A", "pink":   "#EC4899",
}


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------

def go(view: str, **params: Any) -> None:
    """Set the current view + params and rerun."""
    st.query_params.clear()
    st.query_params["view"] = view
    for k, v in params.items():
        st.query_params[k] = str(v)
    st.rerun()


def back_button(label: str = "‹ back to feed") -> None:
    st.markdown("<div class='back-link'>", unsafe_allow_html=True)
    try:
        if st.button(label, key=f"back-{label}", type="secondary"):
            go("feed")
    finally:
        st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Primitives (HTML fragments mirroring artemis-system.jsx)
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


def _hue_for(name: str | None) -> int:
    s = name or "?"
    return sum(ord(c) for c in s) % 360


def avatar(name: str | None, *, size: int = 36) -> str:
    """Squircle avatar with deterministic per-name hue (matches Avatar in JSX)."""
    hue = _hue_for(name)
    return (
        f'<div class="ava" style="'
        f'width:{size}px;height:{size}px;border-radius:{size * 0.28:.1f}px;'
        f'background:linear-gradient(180deg, oklch(0.78 0.07 {hue}) 0%, oklch(0.55 0.10 {hue}) 100%);'
        f'font-size:{size * 0.36:.1f}px;'
        f'">{_initials(name)}</div>'
    )


def pill(text: str, *, tone: str = "neutral", size: str = "md") -> str:
    return f'<span class="pill {size} {tone}">{text}</span>'


def send_pill(sent: bool) -> str:
    if sent:
        return '<span class="pill md send"><span class="dot"></span>Send</span>'
    return '<span class="pill md attempt">Attempt</span>'


def color_chip(color: str | None, *, size: int = 16) -> str:
    swatch = _COLOR_SWATCHES.get((color or "").lower(), "#888")
    cls_size = {12: "x12", 14: "x14", 16: "", 18: "x18", 22: "x22", 24: "x24"}.get(size, "")
    return (
        f'<span class="chip {cls_size}" style="background:'
        f"radial-gradient(circle at 35% 28%, rgba(255,255,255,0.75) 0%, rgba(255,255,255,0) 35%), {swatch};"
        f'"></span>'
    )


def grade_badge(color: str | None, *, gym: str = G.DEFAULT_GYM, size: str = "md") -> str:
    g = G.lookup(color, gym=gym)
    grade = g["grade"] if g else "—"
    label = (g["label"] if g else "").lower()
    chip_size = 22 if size == "lg" else 16
    return (
        f'<span class="grade {size}">'
        f'{color_chip(color, size=chip_size)}'
        f'<span class="g">{grade}</span>'
        f'<span class="l">{label}</span>'
        f'</span>'
    )


def stat_tile(value: str, label: str, *, unit: str | None = None, big: bool = False) -> str:
    cls = "stat-tile big" if big else "stat-tile"
    unit_html = f'<span class="u">{unit}</span>' if unit else ""
    return (
        f'<div class="{cls}">'
        f'<div class="value">{value}{unit_html}</div>'
        f'<div class="label">{label}</div>'
        f'</div>'
    )


def section_head(text: str, *, action: str | None = None, action_href: str | None = None) -> str:
    action_html = ""
    if action:
        if action_href:
            action_html = f'<a class="a" href="{action_href}" style="text-decoration:none;">{action}</a>'
        else:
            action_html = f'<span class="a">{action}</span>'
    return (
        f'<div class="section-h">'
        f'<div class="t">{text}</div>'
        f'<div class="rule"></div>'
        f'{action_html}</div>'
    )


# ---------------------------------------------------------------------------
# Hero video — inline HTML5 <video> with glass-chip overlay
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _video_data_uri(path_str: str, mime: str = "video/mp4") -> str:
    raw = Path(path_str).read_bytes()
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def hero_video(
    src_path: Path | None,
    *,
    climber: str,
    time_label: str,
    sent: bool | None,
    label: str = "highlight",
    height: int = 300,
    show_play: bool = True,
) -> str:
    """Render a full-bleed video with 4 glass chips (top L/R, bottom L/R) +
    centred play button. The play button + dblclick handlers are wired by
    the global script injected in ``inject_fullscreen_script()`` — Streamlit's
    HTML sanitiser strips inline ``onclick``, so we delegate via classes."""
    if src_path and src_path.exists():
        try:
            uri = _video_data_uri(str(src_path))
            video_html = (
                f'<video preload="metadata" muted playsinline controls '
                f'style="height:{height}px;width:100%;object-fit:cover;background:#1A1A1A;">'
                f'<source src="{uri}" type="video/mp4"></video>'
            )
        except OSError:
            video_html = f'<div style="height:{height}px;background:#1A1A1A;"></div>'
    else:
        video_html = f'<div style="height:{height}px;background:#1A1A1A;"></div>'

    send_html = ""
    if sent is True:
        send_html = '<span class="pill md send"><span class="dot"></span>Send</span>'
    elif sent is False:
        send_html = '<span class="pill md attempt">Attempt</span>'

    top = (
        f'<div class="overlay-top">'
        f'  <span class="glass"><span class="live"></span>{climber} · '
        f'  <span class="mono">{time_label}</span></span>'
        f'  {send_html}'
        f'</div>'
    )
    bot = (
        f'<div class="overlay-bot">'
        f'  <span class="glass"><span class="caps">{label}</span></span>'
        f'  <span class="glass">▶ <span class="mono">0:00 / {time_label}</span></span>'
        f'</div>'
    )
    play = (
        '<button type="button" class="play" aria-label="play fullscreen">▶</button>'
        if show_play else ""
    )

    return (
        f'<div class="hero" style="height:{height}px;">'
        f'  {video_html}{top}{bot}{play}'
        f'</div>'
    )


# Global script that opens a lightbox modal in the parent Streamlit DOM
# when the user clicks a hero .play button. The modal shows the video at
# its native aspect ratio (object-fit: contain) on a dark backdrop with
# blur. Click backdrop or × to close, ESC also closes. Injected once per
# page via st.components.v1.html iframe because st.markdown strips
# <script> and onclick attributes.
_FULLSCREEN_SCRIPT_HTML = """
<script>
(function() {
  var w = window.parent || window;
  var doc = w.document;

  function close(overlay) {
    var v = overlay.querySelector('video');
    if (v) { try { v.pause(); } catch (e) {} }
    overlay.remove();
    doc.body.style.overflow = '';
  }

  function open(srcUrl) {
    if (!srcUrl) return;
    // If a modal is already open, close it before opening another.
    var existing = doc.querySelector('.artemis-modal');
    if (existing) close(existing);

    var overlay = doc.createElement('div');
    overlay.className = 'artemis-modal';
    overlay.innerHTML = ''
      + '<div class="artemis-modal-backdrop"></div>'
      + '<div class="artemis-modal-frame">'
      +   '<button type="button" class="artemis-modal-close" aria-label="close">&times;</button>'
      +   '<video class="artemis-modal-video" controls autoplay playsinline src="'
      +     srcUrl + '"></video>'
      + '</div>';

    function onKey(e) {
      if (e.key === 'Escape') {
        close(overlay);
        doc.removeEventListener('keydown', onKey);
      }
    }
    overlay.querySelector('.artemis-modal-backdrop')
      .addEventListener('click', function() { close(overlay); });
    overlay.querySelector('.artemis-modal-close')
      .addEventListener('click', function() { close(overlay); });
    doc.addEventListener('keydown', onKey);

    doc.body.style.overflow = 'hidden';
    doc.body.appendChild(overlay);
  }

  function srcFor(v) {
    if (v.currentSrc) return v.currentSrc;
    var s = v.querySelector('source');
    return s ? s.src : '';
  }

  function bindBtn(btn) {
    if (btn.dataset.popBound) return;
    btn.dataset.popBound = '1';
    btn.addEventListener('click', function(ev) {
      ev.preventDefault();
      var hero = btn.closest('.hero');
      var v = hero && hero.querySelector('video');
      if (v) open(srcFor(v));
    });
  }
  function bindVid(v) {
    if (v.dataset.popBound) return;
    v.dataset.popBound = '1';
    v.addEventListener('dblclick', function() { open(srcFor(v)); });
  }
  function scan() {
    doc.querySelectorAll('.hero .play').forEach(bindBtn);
    doc.querySelectorAll('.hero video').forEach(bindVid);
  }
  scan();
  try {
    new MutationObserver(scan).observe(doc.body, { childList: true, subtree: true });
  } catch (e) {}
})();
</script>
"""


def inject_fullscreen_script() -> None:
    """Mount the pop-out modal binder once per page. Cheap to call multiple
    times — the script's MutationObserver re-binds new buttons automatically."""
    from streamlit.components.v1 import html as _stc_html

    _stc_html(_FULLSCREEN_SCRIPT_HTML, height=0)


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

def _activity_title(row: dict[str, Any]) -> str:
    return titles.display_title(row)


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


def _stat_value(v: Any, *, fmt: str = "{:g}", default: str = "—") -> str:
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return fmt.format(v)
    return str(v)


# ---------------------------------------------------------------------------
# Kudos (likes)
# ---------------------------------------------------------------------------

def _session_id() -> str:
    """Mirror of main.py — read-only convenience for view code."""
    return st.session_state.get("_session_id", "")


def _like_href(attempt_id: int) -> str:
    """Round-trip the current URL so main() can toggle the kudo and bounce
    the user back to the same page."""
    keep = {k: v for k, v in st.query_params.items() if k != "like"}
    qs = [f"like={attempt_id}"] + [f"{k}={v}" for k, v in keep.items()]
    return "?" + "&".join(qs)


def like_button(attempt_id: int, count: int, *, liked: bool) -> str:
    """Render the heart-shaped like control. ``liked`` swaps the glyph and
    flips the pill to its red/active state."""
    glyph = "♥" if liked else "♡"
    cls = "like on" if liked else "like"
    return (
        f'<a class="{cls}" href="{_like_href(attempt_id)}" target="_self" '
        f'aria-label="{"unlike" if liked else "like"} climb {attempt_id}">'
        f'<span class="heart">{glyph}</span>'
        f'<span class="n">{count}</span></a>'
    )


def _kudos_state(attempt_ids: list[int]) -> tuple[dict[int, int], set[int]]:
    """Return ``(counts, liked_ids)`` for the given ids — single round-trip
    for the feed."""
    ids = tuple(sorted(set(int(i) for i in attempt_ids if i)))
    if not ids:
        return {}, set()
    counts = queries.kudos_counts(ids)
    liked = queries.my_kudos(ids, _session_id())
    return counts, liked


# ===========================================================================
# FEED
# ===========================================================================

def feed_view() -> None:
    scope = st.query_params.get("scope", "following")
    mode = st.query_params.get("mode", "cards")

    rows = queries.feed()
    counts = {
        "following": min(len(rows), 12),
        "my gym": sum(1 for r in rows if (r.get("gym_name") or "") == G.DEFAULT_GYM),
        "kc akalla": sum(1 for r in rows if (r.get("gym_name") or "").lower().startswith("klätter")),
        "global": len(rows),
    }
    filter_html = ['<div class="filter-row">']
    for label, key in [
        ("following", "following"),
        ("my gym", "my gym"),
        ("kc akalla", "kc akalla"),
        ("global", "global"),
    ]:
        on = " on" if scope == key else ""
        n = counts.get(key, 0)
        n_disp = f"{n / 1000:.1f}k" if n >= 1000 else str(n)
        href = f"?view=feed&mode={mode}&scope={key}"
        filter_html.append(
            f'<a href="{href}" class="fp{on}" target="_self" style="text-decoration:none;">'
            f'{label}<span class="n">{n_disp}</span></a>'
        )
    filter_html.append("</div>")
    st.markdown("\n".join(filter_html), unsafe_allow_html=True)

    # Today's leaderboard hero — derive from the fastest send of any feed row.
    fastest = next((r for r in rows if r.get("send")), None)
    if fastest:
        color = fastest.get("route_color") or "red"
        time_str = f"{fastest.get('time_seconds') or 0:.1f}s"
        contenders = [r for r in rows if r.get("route_color") == color][:4]
        avatars = "".join(avatar(r.get("climber_name"), size=28) for r in contenders)
        extra = max(0, len(rows) - len(contenders))
        more = f'<span class="more">+ {extra} more</span>' if extra else ""
        st.markdown(
            f"""
            <div class="amber-panel" style="margin-bottom:14px;">
              <div class="eyebrow">today · {color} wall</div>
              <div class="title">{len(contenders)} climbers chasing {time_str}</div>
              <div class="ava-stack">{avatars}{more}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Section head + segmented mode toggle (cards / list).
    cards_on = "on" if mode != "list" else ""
    list_on = "on" if mode == "list" else ""
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;margin:14px 0 8px;">
          <div style="font-family:var(--font);font-size:10.5px;font-weight:700;
                      letter-spacing:0.12em;text-transform:uppercase;color:var(--muted);">
            {scope} · recent climbs
          </div>
          <div style="flex:1;height:1px;background:var(--hairline);"></div>
          <div class="seg">
            <a target="_self" class="{cards_on}" href="?view=feed&mode=cards&scope={scope}">cards</a>
            <a target="_self" class="{list_on}" href="?view=feed&mode=list&scope={scope}">list</a>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not rows:
        st.markdown(
            """
            <div class="amber-panel" style="text-align:center;padding:28px 18px;">
              <div class="eyebrow">your feed is empty</div>
              <div class="title" style="margin-top:6px;">drop your first clip</div>
              <div style="font-size:12px;color:var(--ink-2);margin-top:6px;">
                tap <strong>+ upload</strong> up top — we'll detect pose, time the send,
                score smoothness, and cut a highlight.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    counts, liked = _kudos_state([r.get("attempt_id") for r in rows])
    if mode == "list":
        _feed_list(rows, counts=counts, liked=liked)
    else:
        _chumbox_ad(slot=0)
        for i, r in enumerate(rows):
            aid = int(r.get("attempt_id") or 0)
            _feed_card(r, kudos=counts.get(aid, 0), is_liked=aid in liked)
            if (i + 1) % 2 == 0:
                _chumbox_ad(slot=(i // 2) + 1)


_SPECIFIC_URL = "https://specific.dev/"

_CLIMBING_ADS: list[dict[str, str]] = [
    {"img": "https://picsum.photos/seed/chum-a/240/180",
     "headline": "1 weird trick climbers use to send V12 (gyms hate it)",
     "src": "FlashHacks.co", "href": "#"},
    {"img": "https://picsum.photos/seed/chum-b/240/180",
     "headline": "Local belayer's $4 chalk swap shocks pros",
     "src": "CragDaily", "href": "#"},
    {"img": "https://picsum.photos/seed/chum-c/240/180",
     "headline": "Doctors stunned: this finger move adds 2 grades overnight",
     "src": "TendonTimes", "href": "#"},
    {"img": "https://picsum.photos/seed/chum-d/240/180",
     "headline": "She climbed once a week. What happened next will shock you.",
     "src": "BetaBuzz", "href": "#"},
    {"img": "https://picsum.photos/seed/chum-e/240/180",
     "headline": "Top 7 hangboards banned in 3 countries — see #4",
     "src": "PumpFeed", "href": "#"},
    {"img": "https://picsum.photos/seed/chum-f/240/180",
     "headline": "This routesetter retired at 29. Here's his secret.",
     "src": "SendMoney", "href": "#"},
]

_SPECIFIC_ADS: list[dict[str, str]] = [
    {"img": "https://picsum.photos/seed/specific-a/240/180",
     "headline": "1 weird trick devs use to ship infra in minutes (AWS hates it)",
     "src": "specific.dev", "href": _SPECIFIC_URL},
    {"img": "https://picsum.photos/seed/specific-b/240/180",
     "headline": "This founder replaced his DevOps team with one .hcl file",
     "src": "specific.dev", "href": _SPECIFIC_URL},
    {"img": "https://picsum.photos/seed/specific-c/240/180",
     "headline": "Doctors stunned: `specific dev` boots a full stack overnight",
     "src": "specific.dev", "href": _SPECIFIC_URL},
    {"img": "https://picsum.photos/seed/specific-d/240/180",
     "headline": "She wrote Terraform once. What happened next will shock you.",
     "src": "specific.dev", "href": _SPECIFIC_URL},
    {"img": "https://picsum.photos/seed/specific-e/240/180",
     "headline": "Top 7 IaC tools banned in 3 countries — see #4 (it's Specific)",
     "src": "specific.dev", "href": _SPECIFIC_URL},
    {"img": "https://picsum.photos/seed/specific-f/240/180",
     "headline": "Local SRE retired at 29 after running `specific check`",
     "src": "specific.dev", "href": _SPECIFIC_URL},
]


def _chum_slide(ad: dict[str, str], delay_ms: int) -> str:
    target = ' target="_blank"' if ad["href"].startswith("http") else ""
    return (
        f'<a class="chum-slide" href="{ad["href"]}"{target} rel="noopener sponsored"'
        f' style="animation-delay:{delay_ms}ms;">'
        f'<div class="chum-img" style="background-image:url(\'{ad["img"]}\');"></div>'
        f'<div class="chum-headline">{ad["headline"]}</div>'
        f'<div class="chum-src">{ad["src"]} · Sponsored</div>'
        f'</a>'
    )


def _chumbox_ad(slot: int = 0) -> None:
    """4-tile chumbox; each tile crossfades between a climbing ad and a
    specific.dev ad, staggered so the grid feels alive."""
    nc = len(_CLIMBING_ADS)
    ns = len(_SPECIFIC_ADS)
    tiles_html: list[str] = []
    for k in range(4):
        climb = _CLIMBING_ADS[(slot * 4 + k) % nc]
        spec = _SPECIFIC_ADS[(slot * 4 + k) % ns]
        front, back = (climb, spec) if k % 2 == 0 else (spec, climb)
        stagger = k * 700
        slides = _chum_slide(front, stagger) + _chum_slide(back, stagger - 4000)
        tiles_html.append(f'<div class="chum-tile">{slides}</div>')
    html = (
        '<div class="chum-card" role="complementary" aria-label="Sponsored content">'
        '<div class="chum-label">Promoted Stories · Ads by Specific</div>'
        f'<div class="chum-grid">{"".join(tiles_html)}</div>'
        '<div class="chum-disclaimer">Sponsored by '
        f'<a href="{_SPECIFIC_URL}" target="_blank" rel="noopener sponsored"'
        ' style="color:#0033aa;text-decoration:underline;">specific.dev</a>'
        '</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _feed_card(r: dict[str, Any], *, kudos: int = 0, is_liked: bool = False) -> None:
    climber = r.get("climber_name") or "Unknown climber"
    gym = r.get("gym_name") or "Unknown gym"
    age = _format_age(r.get("posted_at"))
    title = _activity_title(r)
    color = r.get("route_color")
    highlight = r.get("highlight_path")
    src_path = Path(highlight) if highlight else None
    time_str = _stat_value(r.get("time_seconds"), fmt="{:.1f}s")
    first = climber.split()[0] if climber else "—"
    aid = int(r.get("attempt_id") or 0)

    st.markdown(
        f"""
        <div class="card">
          <div class="card-head">
            {avatar(climber, size=36)}
            <div class="meta">
              <div class="name">{climber}</div>
              <div class="sub">{age} · {gym}</div>
            </div>
            {send_pill(bool(r.get("send")))}
          </div>
          <div class="card-title">{title}</div>
          <div class="card-chips">{grade_badge(color)}</div>
          {hero_video(src_path, climber=first, time_label=time_str,
                      sent=bool(r.get("send")), label="highlight",
                      height=300)}
          <div class="stat-row">
            {stat_tile(_stat_value(r.get("time_seconds"), fmt="{:.1f}"), "time", unit="s")}
            {stat_tile(_stat_value(r.get("smoothness_pct"), fmt="{:.0f}"), "smooth")}
            {stat_tile(_stat_value(r.get("dynamic_moves"), fmt="{:d}"), "dyno")}
            {stat_tile(_stat_value(r.get("hang_time_seconds"), fmt="{:.1f}"), "hang", unit="s")}
          </div>
          <div class="card-foot">
            {like_button(aid, kudos, liked=is_liked)}
            <a target="_self" href="?view=post&attempt_id={aid}" class="open"
               style="text-decoration:none;">open ›</a>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _feed_list(
    rows: list[dict[str, Any]],
    *,
    counts: dict[int, int] | None = None,
    liked: set[int] | None = None,
) -> None:
    """Hacker-News-style dense ranked list. Sorted by real like count, with
    DB order as a tiebreaker (recency)."""
    counts = counts or {}
    liked = liked or set()
    ranked = sorted(rows, key=lambda r: -counts.get(int(r.get("attempt_id") or 0), 0))
    parts = ['<div class="hn">']
    for i, r in enumerate(ranked, start=1):
        climber = r.get("climber_name") or "Unknown climber"
        gym = (r.get("gym_name") or "Unknown gym")
        age = _format_age(r.get("posted_at"))
        color = r.get("route_color")
        g = G.lookup(color)
        grade = g["grade"] if g else "—"
        title = _activity_title(r)
        time_str = _stat_value(r.get("time_seconds"), fmt="{:.1f}s")
        aid = int(r.get("attempt_id") or 0)
        pts = counts.get(aid, 0)
        top_cls = f" top{i}" if i <= 3 else ""
        cid = r.get("climber_id")
        climber_link = (
            f'<a target="_self" href="?view=profile&climber_id={cid}" '
            f'style="text-decoration:none;color:inherit;" '
            f'class="who">{climber.lower()}</a>'
            if cid is not None else f'<span class="who">{climber.lower()}</span>'
        )
        parts.append(
            f'<div class="hn-row{top_cls}">'
            f'  <a target="_self" href="?view=post&attempt_id={aid}" class="rank" '
            f'     style="text-decoration:none;color:inherit;">{i}.</a>'
            f'  <a target="_self" href="?view=post&attempt_id={aid}" '
            f'     style="text-decoration:none;color:inherit;">{color_chip(color, size=14)}</a>'
            f'  <a target="_self" href="?view=post&attempt_id={aid}" '
            f'     style="text-decoration:none;color:inherit;">'
            f'    <div class="title">{title}'
            f'      <span class="grade-inline">{grade}</span></div>'
            f'    <div class="meta">'
            f'      by {climber_link} · {gym.lower()} · {age} · '
            f'      <span class="mono">{time_str}</span>'
            f'    </div>'
            f'  </a>'
            f'  <div class="right">{like_button(aid, pts, liked=aid in liked)}'
            f'    {send_pill(bool(r.get("send")))}'
            f'  </div>'
            f'</div>'
        )
    parts.append("</div>")
    st.markdown("\n".join(parts), unsafe_allow_html=True)


# ===========================================================================
# POST DETAIL
# ===========================================================================

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
    title = _activity_title(a)
    highlight = a.get("highlight_path")
    src_path = Path(highlight) if highlight else None
    has_hero = bool(src_path and src_path.exists())
    time_str = _stat_value(a.get("time_seconds"), fmt="{:.1f}s")
    first = climber.split()[0] if climber else "—"
    cid = a.get("climber_id")

    # ----- Hero video (full-bleed inside a card)
    if has_hero:
        st.markdown(
            f"""
            <div class="card" style="margin-bottom:14px;">
              {hero_video(src_path, climber=first, time_label=time_str,
                          sent=bool(a.get("send")), label="highlight",
                          height=360)}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ----- Climber row
    profile_href = f"?view=profile&climber_id={cid}" if cid is not None else "#"
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:12px;
                    padding:0 2px 6px;margin-bottom:8px;">
          <a href="{profile_href}" target="_self" style="text-decoration:none;color:inherit;
                                           display:flex;align-items:center;gap:12px;flex:1;">
            {avatar(climber, size=44)}
            <div>
              <div style="font-family:var(--font);font-weight:800;font-size:16px;
                          letter-spacing:-0.02em;color:var(--ink);">{climber}</div>
              <div style="font-family:var(--font);font-size:12px;color:var(--muted);
                          font-weight:600;">{age} · {gym}</div>
            </div>
          </a>
          {pill("follow", tone="neutral", size="md")}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ----- Title + grade row
    st.markdown(
        f"""
        <h1 class="page-h1" style="font-size:clamp(22px, 6vw, 26px);
                                    margin: 6px 0 10px;">{title}</h1>
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;
                    margin-bottom:18px;">
          {grade_badge(color, size="lg")}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ----- Stats grid (3 x 2 big tiles)
    st.markdown(section_head("stats"), unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="stat-grid" style="margin-bottom:18px;">
          {stat_tile(_stat_value(a.get("time_seconds"), fmt="{:.1f}"), "time to top", unit="s", big=True)}
          {stat_tile(_stat_value(a.get("smoothness_pct"), fmt="{:.0f}"), "smoothness", big=True)}
          {stat_tile(_stat_value(a.get("dynamic_moves"), fmt="{:d}"), "dyno moves", big=True)}
          {stat_tile(_stat_value(a.get("longest_reach_px"), fmt="{:.0f}"), "longest reach", unit="px", big=True)}
          {stat_tile(_stat_value(a.get("hang_time_seconds"), fmt="{:.1f}"), "hang · hardest", unit="s", big=True)}
          {stat_tile(_stat_value(a.get("idle_seconds"), fmt="{:.1f}"), "idle / rest", unit="s", big=True)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ----- Full climb · route overlay (full hero treatment + pop-out modal,
    # matches the highlight clip up top).
    overlay = a.get("overlay_path")
    overlay_path = Path(overlay) if overlay else None
    if overlay_path and overlay_path.exists():
        st.markdown(section_head("full climb · route overlay"), unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="card" style="margin-bottom:10px;">
              {hero_video(overlay_path, climber=first, time_label=time_str,
                          sent=bool(a.get("send")),
                          label=f"route overlay · {time_str}",
                          height=320)}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div style="display:flex;gap:8px;margin:10px 0 6px;flex-wrap:wrap;">
              <span class="pill sm neutral"><span class="dot"></span>route overlay on</span>
              <span class="pill sm neutral">holds off</span>
              <span class="pill sm neutral">0.5×</span>
              <span class="pill sm neutral">1×</span>
              <span class="pill sm ink">2×</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ----- Movement timeline
    st.markdown(section_head("movement timeline"), unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="card timeline-card">
          {_sparkline_svg()}
          <div class="timeline-x">
            <span>0s</span><span>10s</span><span>20s</span>
            <span>30s</span><span>{time_str}</span>
          </div>
          <div class="move-chips">
            <span class="at">0:04</span><span class="pill sm neutral">start</span>
            <span class="at">0:09</span><span class="pill sm amber">dyno</span>
            <span class="at">0:18</span><span class="pill sm neutral">heel hook</span>
            <span class="at">0:24</span><span class="pill sm neutral">rest 4.1s</span>
            <span class="at">0:33</span><span class="pill sm send">top-out</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not has_hero and not (overlay_path and overlay_path.exists()):
        st.caption("No video available for this attempt yet.")


def _sparkline_svg() -> str:
    """Static jerk-over-time sparkline (amber stroke, gradient fill)."""
    pts = [
        (0, 40), (20, 38), (40, 32), (60, 30), (80, 12),
        (100, 28), (120, 30), (140, 28), (160, 22), (180, 24),
        (200, 30), (220, 40), (240, 38), (260, 18), (280, 24),
        (300, 28), (320, 30),
    ]
    d_line = "M " + " L ".join(f"{x} {y}" for x, y in pts)
    d_area = d_line + " L 320 56 L 0 56 Z"
    return (
        '<svg viewBox="0 0 320 56" width="100%" height="56" preserveAspectRatio="none">'
        '<defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#FF9A1F" stop-opacity="0.25"/>'
        '<stop offset="100%" stop-color="#FF9A1F" stop-opacity="0"/>'
        '</linearGradient></defs>'
        f'<path d="{d_area}" fill="url(#sg)"/>'
        f'<path d="{d_line}" stroke="#F47A00" stroke-width="1.6" fill="none" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    )


# ===========================================================================
# PROFILE
# ===========================================================================

def profile_view(climber_id: int) -> None:
    # The nav-bar "profile" hold-button doesn't know which climber to open
    # (no auth yet). When no id is passed we show a directory of every
    # climber in the gym instead of an error.
    if not climber_id:
        _climber_picker()
        return
    c = queries.climber(climber_id)
    if c is None:
        st.markdown(
            f'<div class="amber-panel" style="text-align:center;padding:24px 18px;">'
            f'<div class="eyebrow">climber not found</div>'
            f'<div class="title" style="margin-top:6px;">id {climber_id} doesn\'t '
            f'match anyone in this gym</div>'
            f'<div style="font-size:12px;color:var(--ink-2);margin-top:6px;">'
            f'pick someone from the list below.</div></div>',
            unsafe_allow_html=True,
        )
        _climber_picker()
        return

    back_button()

    name = c["name"]
    sends = c.get("sends") or 0
    attempts = c.get("attempts_logged") or 0
    fastest = c.get("fastest_send_seconds")

    # ----- Amber-tinted header zone
    st.markdown(
        f"""
        <div class="amber-panel" style="padding:20px 16px 16px;margin-bottom:14px;">
          <div style="display:flex;align-items:center;gap:14px;margin-bottom:14px;">
            {avatar(name, size=64)}
            <div>
              <div style="font-family:var(--font);font-size:22px;font-weight:800;
                          letter-spacing:-0.025em;line-height:1.1;color:var(--ink);">{name}</div>
              <div style="font-family:var(--font);font-size:12px;color:var(--muted);
                          font-weight:600;margin-top:2px;">indoor boulderer · {G.DEFAULT_GYM.lower()}</div>
              <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;">
                <span class="pill sm amber">⌃ {sends * 17} kudos</span>
                <span class="pill sm neutral">personal best</span>
              </div>
            </div>
          </div>
          <div class="stat-grid" style="grid-template-columns: repeat(3, 1fr);
                                         border-radius:18px;border:1px solid var(--hairline);">
            {stat_tile(_stat_value(sends, fmt="{:d}", default="0"), "sends · 30d", big=True)}
            {stat_tile(_stat_value(attempts, fmt="{:d}", default="0"), "attempts", big=True)}
            {stat_tile(_stat_value(fastest, fmt="{:.1f}", default="—"), "fastest send",
                       unit=("s" if fastest else None), big=True)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ----- Grade pyramid
    rows = queries.climber_attempts(climber_id)
    pyramid = _pyramid_data(rows)
    st.markdown(section_head("grade pyramid · 30d", action="all time"), unsafe_allow_html=True)
    pyramid_rows = []
    for d in pyramid:
        swatch = _COLOR_SWATCHES.get(d["color"], "#888")
        pct = (d["n"] / d["max"] * 100) if d["max"] else 0
        pyramid_rows.append(
            f'<div class="row">'
            f'  <div class="label">{color_chip(d["color"], size=12)} {d["grade"]}</div>'
            f'  <div class="bar"><div class="fill" style="width:{pct:.0f}%;'
            f'    background:linear-gradient(180deg, {swatch}DD, {swatch});"></div></div>'
            f'  <div class="n">{d["n"]}</div>'
            f'</div>'
        )
    st.markdown(
        f'<div class="card pyramid">{"".join(pyramid_rows)}</div>',
        unsafe_allow_html=True,
    )

    # ----- Recent climbs (dense rows)
    st.markdown(section_head("recent climbs"), unsafe_allow_html=True)
    if not rows:
        st.caption("No climbs logged yet.")
        return

    list_html = ['<div class="row-list">']
    for r in rows:
        color = r.get("route_color")
        g = G.lookup(color)
        grade = g["grade"] if g else "—"
        gym = (r.get("gym_name") or "—").lower()
        age = _format_age(r.get("posted_at"))
        time_str = _stat_value(r.get("time_seconds"), fmt="{:.1f}s")
        list_html.append(
            f'<a target="_self" class="row" href="?view=post&attempt_id={r["attempt_id"]}" '
            f' style="text-decoration:none;color:inherit;">'
            f'  {color_chip(color, size=18)}'
            f'  <div class="body">'
            f'    <div class="t">{grade} · climb #{r["attempt_id"]}</div>'
            f'    <div class="s">{age} · {gym}</div>'
            f'  </div>'
            f'  <div class="time">{time_str}</div>'
            f'  {send_pill(bool(r.get("send")))}'
            f'</a>'
        )
    list_html.append("</div>")
    st.markdown("\n".join(list_html), unsafe_allow_html=True)


def _climber_picker() -> None:
    """Directory rendered when a profile URL has no climber_id (the nav tab
    case). Shows every climber as a card; clicking drills into their profile."""
    st.markdown(
        '<h1 class="page-h1">climbers</h1>'
        '<div class="page-sub">pick a climber to see their profile, grade '
        'pyramid, and recent sends.</div>',
        unsafe_allow_html=True,
    )
    climbers = queries.climbers()
    if not climbers:
        st.markdown(
            '<div class="amber-panel" style="text-align:center;padding:28px 18px;">'
            '<div class="eyebrow">no climbers yet</div>'
            '<div class="title" style="margin-top:6px;">upload your first clip</div>'
            '<div style="font-size:12px;color:var(--ink-2);margin-top:6px;">'
            'every uploaded climber gets a profile auto-generated.</div></div>',
            unsafe_allow_html=True,
        )
        return
    tiles = []
    for c in climbers:
        name = c["name"]
        sends = int(c.get("sends") or 0)
        attempts = int(c.get("attempts_logged") or 0)
        fastest = c.get("fastest_send_seconds")
        meta = f"{sends} send{'s' if sends != 1 else ''} · {attempts} attempt{'s' if attempts != 1 else ''}"
        pin = f"{fastest:.1f}s" if fastest else "—"
        tiles.append(
            f'<a target="_self" class="climber-tile" '
            f'href="?view=profile&climber_id={c["id"]}">'
            f'  {avatar(name, size=44)}'
            f'  <div class="meta">'
            f'    <div class="n">{name}</div>'
            f'    <div class="s">{meta}</div>'
            f'  </div>'
            f'  <div class="pin">{pin}</div>'
            f'</a>'
        )
    st.markdown(
        f'<div class="climbers-grid">{"".join(tiles)}</div>',
        unsafe_allow_html=True,
    )


def _pyramid_data(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group climber attempts by grade row (highest first)."""
    grade_rows = [
        ("V7-V8", "black"),
        ("V6-V7", "purple"),
        ("V5-V6", "red"),
        ("V4-V5", "blue"),
        ("V3-V4", "green"),
        ("V1",    "yellow"),
    ]
    table = G.COLOR_GRADES[G.DEFAULT_GYM]
    counts: dict[str, int] = {g: 0 for g, _ in grade_rows}
    for r in rows:
        color = (r.get("route_color") or "").lower()
        meta = table.get(color)
        if not meta:
            continue
        grade = meta["grade"]
        if grade in counts:
            counts[grade] += 1
    max_n = max(counts.values()) or 1
    return [{"grade": g, "color": c, "n": counts[g], "max": max_n} for g, c in grade_rows]


# ===========================================================================
# LEADERBOARDS (lightweight new view — reuses HN list style)
# ===========================================================================

def leaderboards_view() -> None:
    rows = queries.feed()
    sends = [r for r in rows if r.get("send") and r.get("time_seconds") is not None]
    sends.sort(key=lambda r: r["time_seconds"])
    colors_with_sends = sorted({(r.get("route_color") or "—") for r in sends})

    st.markdown(
        f'<h1 class="page-h1">leaderboards</h1>'
        f'<div class="page-sub">{len(sends)} sends across {len(colors_with_sends)} '
        f'route{"s" if len(colors_with_sends) != 1 else ""} — fastest first, updated '
        f'as climbs come in.</div>',
        unsafe_allow_html=True,
    )

    if not sends:
        st.markdown(
            '<div class="amber-panel" style="text-align:center;padding:32px 18px;">'
            '<div class="eyebrow">no sends logged yet</div>'
            '<div class="title" style="margin-top:6px;">be the first one up</div>'
            '<div style="font-size:12px;color:var(--ink-2);margin-top:6px;">'
            'upload a clip of a clean topout — fastest time per route claims #1.'
            '</div></div>',
            unsafe_allow_html=True,
        )
        return

    _podium(sends[:3])

    # Per-route boards, grouped by color, sorted by their #1 time (fastest gym
    # leader appears first).
    by_color: dict[str, list[dict[str, Any]]] = {}
    for r in sends:
        c = (r.get("route_color") or "—")
        by_color.setdefault(c, []).append(r)
    colors_sorted = sorted(by_color, key=lambda c: by_color[c][0]["time_seconds"])

    st.markdown(section_head("per-route boards"), unsafe_allow_html=True)
    for color in colors_sorted:
        _per_route_card(color, by_color[color][:5])


def _podium(top3: list[dict[str, Any]]) -> None:
    """Three-column hero panel. Layout is [#2 left, #1 centre taller, #3 right]
    — classic Olympic podium read."""
    # Index by slot: middle column is index 0 (fastest), left is index 1,
    # right is index 2. Pad missing slots with placeholders.
    padded: list[dict[str, Any] | None] = list(top3) + [None] * (3 - len(top3))
    order = [(2, padded[1]), (1, padded[0]), (3, padded[2])]
    cols_html = "".join(_podium_col(rank, r) for rank, r in order)
    title = padded[0].get("climber_name") if padded[0] else "—"
    fastest = f"{padded[0]['time_seconds']:.1f}s" if padded[0] else "—"
    st.markdown(
        f"""
        <div class="podium-wrap">
          <div class="eyebrow">fastest sends · top 3</div>
          <div class="super-title">{title} leads · {fastest}</div>
          <div class="podium-row">{cols_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _podium_col(rank: int, r: dict[str, Any] | None) -> str:
    if not r:
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}[rank]
        return (
            f'<div class="podium-col rank-{rank} empty">'
            f'<div class="medal" style="opacity:0.5">{medal}</div>'
            f'<div style="font-size:12px;font-weight:700;color:var(--muted);'
            f'letter-spacing:0.04em;text-transform:uppercase;">open slot</div>'
            f'</div>'
        )
    name = r.get("climber_name") or "Unknown"
    first = name.split()[0] if name else "—"
    color = r.get("route_color")
    g = G.lookup(color)
    grade = g["grade"] if g else "—"
    t = f"{r['time_seconds']:.1f}"
    aid = r["attempt_id"]
    medal = {1: "🥇", 2: "🥈", 3: "🥉"}[rank]
    ava_size = 56 if rank == 1 else 44
    return (
        f'<a target="_self" class="podium-col rank-{rank}" '
        f'href="?view=post&attempt_id={aid}">'
        f'  <div class="medal">{medal}</div>'
        f'  {avatar(name, size=ava_size)}'
        f'  <div class="name">{first}</div>'
        f'  <div class="time">{t}<span class="u">s</span></div>'
        f'  <div class="grade-row">{color_chip(color, size=12)}<span>{grade}</span></div>'
        f'</a>'
    )


def _per_route_card(color: str, entries: list[dict[str, Any]]) -> None:
    g = G.lookup(color)
    grade = g["grade"] if g else "—"
    label = (g["label"] if g else "").lower()
    rows_html: list[str] = []
    for i, r in enumerate(entries, start=1):
        name = r.get("climber_name") or "Unknown"
        parts = name.split()
        first = parts[0] if parts else "—"
        last = " ".join(parts[1:]) if len(parts) > 1 else ""
        t = f"{r['time_seconds']:.1f}s"
        top_cls = f" top{i}" if i <= 3 else ""
        rows_html.append(
            f'<a target="_self" class="lb-row{top_cls}" '
            f'href="?view=post&attempt_id={r["attempt_id"]}">'
            f'  <div class="rank">{i}.</div>'
            f'  {avatar(name, size=24)}'
            f'  <div class="who">{first}'
            + (f'<span class="last">{last}</span>' if last else "")
            + "</div>"
            f'  <div class="t">{t}</div>'
            f'</a>'
        )
    st.markdown(
        f'<div class="lb-card">'
        f'  <div class="head">'
        f'    {color_chip(color, size=16)}'
        f'    <div class="title">{color} · {grade}</div>'
        f'    <span class="label">{label}</span>'
        f'    <span class="right">top {len(entries)}</span>'
        f'  </div>'
        f'  {"".join(rows_html)}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ===========================================================================
# UPLOAD
# ===========================================================================

def upload_view() -> None:
    back_button()
    st.markdown(
        """
        <h1 class="page-h1">upload a climb</h1>
        <div class="page-sub">30-90 second portrait clip works best. we detect pose,
        time the send, score smoothness, and cut the highlight.</div>
        """,
        unsafe_allow_html=True,
    )

    if "upload_random_title" not in st.session_state:
        st.session_state["upload_random_title"] = titles.random_title()

    title_mode = st.radio(
        "title mode",
        options=("auto", "random", "custom"),
        horizontal=True,
        label_visibility="collapsed",
        key="title_mode",
    )

    custom_title = ""
    if title_mode == "random":
        rcols = st.columns([5, 1])
        with rcols[0]:
            st.text_input(
                "random name",
                value=st.session_state["upload_random_title"],
                disabled=True,
                key="random_preview",
                label_visibility="collapsed",
            )
        with rcols[1]:
            if st.button("↻", key="reroll-title", help="Roll a new name"):
                st.session_state["upload_random_title"] = titles.random_title()
                st.rerun()
    elif title_mode == "custom":
        custom_title = st.text_input(
            "name your climb",
            placeholder="e.g. Wednesday Project, Heel Hook Heaven",
            key="custom_title",
            label_visibility="collapsed",
        )
    else:
        st.caption(
            "we'll name it from the result + grade — e.g. *Sent Red · V5-V6*."
        )

    st.markdown(
        """
        <div class="dropzone" style="margin-bottom:14px;">
          <div class="icon">↑</div>
          <div class="t">drop your clip</div>
          <div class="s">or tap to browse · mp4 / mov / m4v</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("upload-form", clear_on_submit=False):
        uploaded = st.file_uploader(
            "climbing video",
            type=["mp4", "mov", "m4v", "mkv", "webm"],
            accept_multiple_files=False,
            help="Mobile-shot portrait clips up to ~60 s work best.",
        )
        cols = st.columns(2)
        with cols[0]:
            climber_name = st.text_input(
                "climber name", placeholder="e.g. niklavs visockis"
            )
            color_choices = list(G.COLOR_GRADES[G.DEFAULT_GYM].keys())
            color = st.selectbox(
                "hold color · drives the grade",
                options=color_choices,
                index=0,
            )
        with cols[1]:
            gym = st.text_input("gym", value=G.DEFAULT_GYM)
            grade_preview = G.lookup(color, gym=gym)
            if grade_preview:
                st.markdown(
                    f"""
                    <div class="amber-panel" style="padding:12px 14px;">
                      <div class="eyebrow">inferred grade</div>
                      <div style="font-family:var(--font);font-size:34px;font-weight:800;
                                  letter-spacing:-0.03em;color:var(--ink);line-height:1;
                                  margin-top:4px;">{grade_preview['grade']}</div>
                      <div style="font-size:12px;color:var(--ink-2);font-weight:600;
                                  margin-top:2px;">{color} · {grade_preview['label'].lower()}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Grade lookup only configured for Klättercentret Akalla in v1.")

        st.markdown("<div class='cta-full'>", unsafe_allow_html=True)
        submitted = st.form_submit_button(
            "analyze climb", type="primary", use_container_width=True
        )
        st.markdown("</div>", unsafe_allow_html=True)

    if not submitted:
        return
    if uploaded is None:
        st.error("Pick a video file first.")
        return
    if not climber_name.strip():
        st.error("Climber name is required.")
        return

    if title_mode == "random":
        chosen_title: str | None = st.session_state["upload_random_title"]
    elif title_mode == "custom":
        chosen_title = custom_title.strip() or None
    else:
        chosen_title = None

    size_mb = uploaded.size / (1024 * 1024)
    if size_mb > 25:
        st.warning(
            f"Your file is {size_mb:.0f} MB — large clips are usually >2 min "
            "and the tracker fragments. v1 works best on **30-90 second** clips "
            "of one attempt. Continuing anyway."
        )

    attempt_id = _run_upload_pipeline(
        uploaded, climber_name.strip(), color, gym.strip(), chosen_title,
    )
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


def _run_upload_pipeline(
    uploaded: Any,
    climber_name: str,
    color: str,
    gym: str,
    title: str | None,
) -> int | None:
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
            title=title,
        )
