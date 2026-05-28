"""Artemis dashboard — Aqua-modern, Strava-dense.

View selection lives in `st.query_params["view"]` so links are refresh-safe.
Visual system follows the Artemis handoff in
docs/plans/2026-05-28-artemis-ui-strava-layout.md and the JSX reference at
`/home/niklavsvisockis/Downloads/artemis/design_handoff_artemis_ui/`:
- glossy aqua pills + glass overlays
- marble color chips
- amber gradient is the only saturated colour
- SF Pro Display for chrome, SF Mono w/ tabular-nums for stats
"""

from __future__ import annotations

import base64
import uuid
from pathlib import Path

import queries
import streamlit as st
import views

_IMG_DIR = Path(__file__).resolve().parents[2] / "src" / "strava_climbing" / "img"
_LOGO_ICON = _IMG_DIR / "logo.png"
_WORDMARK = _IMG_DIR / "artemis-wordmark.jpeg"
_LOGOTYPE = _IMG_DIR / "artemis-logotype.png"

_NAV_BUTTONS = {
    "feed": _IMG_DIR / "feed_button.png",
    "leaderboards": _IMG_DIR / "boards_button.png",
    "profile": _IMG_DIR / "profile_button.png",
}


def _data_uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


_WORDMARK_URI = (
    _data_uri(_WORDMARK, "image/jpeg")
    if _WORDMARK.exists()
    else (_data_uri(_LOGOTYPE, "image/png") if _LOGOTYPE.exists() else "")
)

_NAV_URIS = {
    view: _data_uri(path, "image/png")
    for view, path in _NAV_BUTTONS.items()
    if path.exists()
}


st.set_page_config(
    page_title="artemis · climb",
    page_icon=str(_LOGO_ICON) if _LOGO_ICON.exists() else None,
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Design system — full Artemis Aqua token set + primitives
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
      :root {
        /* ----- Brand ----- */
        --amber:        #FF9A1F;
        --amber-deep:   #F47A00;
        --amber-soft:   #FFB85A;
        --amber-glow:   rgba(244,122,0,0.35);

        /* ----- Surface ----- */
        --ink:          #11110F;
        --ink-2:        #3A3A37;
        --muted:        #8A8A85;
        --hairline:     rgba(20,20,18,0.08);
        --bg:           #FAF8F4;
        --surface:      #FFFFFF;
        --surface-tint: #FDFBF6;

        /* ----- Send / attempt ----- */
        --send:      oklch(0.66 0.17 145);
        --send-soft: oklch(0.93 0.06 145);
        --send-glow: oklch(0.66 0.17 145 / 0.35);

        /* ----- Type ----- */
        --font: "SF Pro Display", "Inter", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        --mono: "SF Mono", "JetBrains Mono", ui-monospace, Menlo, monospace;

        /* ----- Radii ----- */
        --r-card-lg: 18px;
        --r-card:    16px;
        --r-pill:    999px;
        --r-sq:      10px;

        /* ----- Spacing (8px base) ----- */
        --s-1: 4px;  --s-2: 8px;  --s-3: 12px;
        --s-4: 16px; --s-5: 20px; --s-6: 24px;
        --s-7: 32px; --s-8: 40px;

        --card-pad-x: clamp(14px, 4vw, 16px);
        --card-pad-y: clamp(12px, 3vw, 14px);

        /* ----- Shadow recipes ----- */
        --shadow-card:
          inset 0 1px 0 rgba(255,255,255,0.6),
          0 1px 2px rgba(0,0,0,0.04),
          0 8px 24px rgba(20,15,5,0.05);
      }

      /* ---------- Reset Streamlit chrome ---------- */
      [data-testid="stHeader"], [data-testid="stToolbar"],
      footer, #MainMenu, [data-testid="stSidebar"] {
        display: none !important;
      }
      .block-container {
        padding-top: var(--s-3);
        padding-bottom: var(--s-8);
        padding-left: clamp(12px, 4vw, 24px);
        padding-right: clamp(12px, 4vw, 24px);
        max-width: 760px;
      }
      html, body, [class*="stApp"] {
        background: var(--bg);
        color: var(--ink);
        font-family: var(--font);
        font-weight: 500;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
      }
      h1, h2, h3, h4 { line-height: 1.1; letter-spacing: -0.02em; }
      p, span, div { letter-spacing: -0.005em; line-height: 1.45; text-wrap: pretty; }

      /* tabular numerals on stat tiles */
      .stat-tile .value, .stat-row .value, .stat-grid .value {
        font-variant-numeric: tabular-nums;
        font-feature-settings: "tnum" 1;
      }

      /* ====================================================================
         NavBar (sticky, translucent, backdrop-blur)
         ==================================================================== */
      .brand-row {
        position: sticky; top: 0; z-index: 100;
        background: rgba(250,248,244,0.78);
        backdrop-filter: blur(20px) saturate(180%);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        margin: 0 calc(-1 * clamp(12px, 4vw, 24px)) var(--s-5);
        padding: 10px clamp(12px, 4vw, 24px) 10px;
        border-bottom: 1px solid var(--hairline);
      }
      .brand-row [data-testid="stHorizontalBlock"] {
        align-items: center !important;
        gap: 8px !important;
      }
      .brand-row [data-testid="stColumn"] {
        display: flex; flex-direction: column; justify-content: center;
      }

      .artemis-mark {
        display: flex; align-items: center; gap: 8px;
        line-height: 1; padding: 2px 0;
      }
      .artemis-mark img { height: 30px; width: auto; display: block; }
      .artemis-mark .pretitle {
        font-family: var(--font);
        font-size: 9.5px; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.14em;
        color: var(--muted);
      }

      /* Climbing-hold nav buttons — the route holds become the navigation. */
      .nav-holds {
        display: flex; align-items: center; justify-content: center;
        gap: clamp(8px, 2vw, 16px);
      }
      .nav-hold {
        display: inline-flex; align-items: center; justify-content: center;
        width: clamp(88px, 20vw, 106px);
        height: clamp(88px, 20vw, 106px);
        padding: 0; border-radius: 14px;
        background: transparent; border: none;
        text-decoration: none;
        transition: transform 120ms ease, filter 120ms ease;
        filter: grayscale(0.25) brightness(0.95);
        opacity: 0.85;
      }
      .nav-hold img {
        width: 100%; height: 100%;
        object-fit: contain;
        display: block;
        filter: drop-shadow(0 2px 4px rgba(20,15,5,0.18));
      }
      .nav-hold:hover {
        transform: translateY(-1px);
        filter: grayscale(0) brightness(1);
        opacity: 1;
      }
      .nav-hold.on {
        filter: grayscale(0) brightness(1);
        opacity: 1;
        transform: translateY(-1px);
      }
      .nav-hold.on img {
        filter: drop-shadow(0 4px 10px var(--amber-glow))
                drop-shadow(0 1px 2px rgba(20,15,5,0.25));
      }

      /* ====================================================================
         PILLS — glossy aqua capsules
         ==================================================================== */
      .pill {
        display: inline-flex; align-items: center; gap: 6px;
        height: 24px; padding: 5px 12px;
        border-radius: var(--r-pill);
        font-family: var(--font);
        font-size: 11.5px; font-weight: 700;
        letter-spacing: 0.04em; text-transform: uppercase;
        white-space: nowrap;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.55),
          inset 0 -1px 0 rgba(0,0,0,0.10),
          0 1px 2px rgba(0,0,0,0.05);
      }
      .pill.sm { height: 20px; padding: 3px 9px; font-size: 10.5px; }
      .pill.md { height: 24px; padding: 5px 12px; font-size: 11.5px; }
      .pill.lg { height: 32px; padding: 8px 16px; font-size: 13px; }

      .pill.send {
        background: linear-gradient(180deg, oklch(0.78 0.18 145), oklch(0.58 0.18 145));
        color: white;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.55),
          inset 0 -1px 0 rgba(0,0,0,0.10),
          0 1px 2px var(--send-glow);
      }
      .pill.attempt {
        background: linear-gradient(180deg, oklch(0.96 0.02 60), oklch(0.88 0.02 60));
        color: var(--ink);
      }
      .pill.amber {
        background: linear-gradient(180deg, var(--amber-soft), var(--amber-deep));
        color: white;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.55),
          inset 0 -1px 0 rgba(0,0,0,0.10),
          0 1px 2px var(--amber-glow);
      }
      .pill.neutral {
        background: linear-gradient(180deg, #FFFFFF, #EFEDE8);
        color: var(--ink);
      }
      .pill.ink {
        background: linear-gradient(180deg, #2D2D2A, #151513);
        color: white;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.18),
          inset 0 -1px 0 rgba(0,0,0,0.30),
          0 1px 2px rgba(0,0,0,0.20);
      }
      .pill .dot {
        display: inline-block; width: 6px; height: 6px; border-radius: 50%;
        background: currentColor;
      }

      /* ====================================================================
         COLOR CHIP — glossy marble swatch
         ==================================================================== */
      .chip {
        display: inline-block; width: 16px; height: 16px; border-radius: 50%;
        flex-shrink: 0; vertical-align: middle;
        box-shadow:
          inset 0 -1px 2px rgba(0,0,0,0.25),
          0 0 0 1px rgba(0,0,0,0.08),
          0 1px 2px rgba(0,0,0,0.12);
      }
      .chip.x12 { width: 12px; height: 12px; }
      .chip.x14 { width: 14px; height: 14px; }
      .chip.x18 { width: 18px; height: 18px; }
      .chip.x22 { width: 22px; height: 22px; }
      .chip.x24 { width: 24px; height: 24px; }
      .chip-ring {
        display: inline-flex; padding: 2px; border-radius: 50%;
        box-shadow: 0 0 0 2px var(--amber);
      }

      /* ====================================================================
         GRADE BADGE
         ==================================================================== */
      .grade {
        display: inline-flex; align-items: center; gap: 8px;
        line-height: 1;
      }
      .grade .g {
        font-family: var(--font); font-weight: 800; color: var(--ink);
        letter-spacing: -0.02em; font-size: 14px; line-height: 1;
      }
      .grade .l {
        font-family: var(--font); font-size: 9.5px; font-weight: 700;
        color: var(--muted); letter-spacing: 0.1em; text-transform: uppercase;
      }
      .grade.lg .g { font-size: 18px; }
      .grade.lg .l { font-size: 11px; }

      /* ====================================================================
         SECTION HEAD — lowercase 10.5 caps + hairline + optional action
         ==================================================================== */
      .section-h {
        display: flex; align-items: center; gap: 10px;
        padding: 4px 0; margin: 12px 0 8px;
      }
      .section-h .t {
        font-family: var(--font); font-size: 10.5px; font-weight: 700;
        letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted);
      }
      .section-h .rule {
        flex: 1; height: 1px; background: var(--hairline);
      }
      .section-h .a {
        font-family: var(--font); font-size: 11px; font-weight: 600;
        color: var(--amber-deep); cursor: pointer;
      }

      /* ====================================================================
         AVATAR — squircle, deterministic per-name hue
         ==================================================================== */
      .ava {
        display: inline-grid; place-items: center; flex-shrink: 0;
        color: white; font-family: var(--font); font-weight: 700;
        letter-spacing: -0.02em;
        text-shadow: 0 1px 0 rgba(0,0,0,0.18);
        position: relative; overflow: hidden;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.5),
          inset 0 -1px 0 rgba(0,0,0,0.18),
          0 1px 2px rgba(0,0,0,0.08);
      }
      .ava::after {
        content: ""; position: absolute; inset: 1px;
        border-radius: inherit;
        background: linear-gradient(180deg, rgba(255,255,255,0.35), rgba(255,255,255,0) 50%);
        pointer-events: none;
      }

      /* ====================================================================
         GLASS CHIP — translucent pill over video
         ==================================================================== */
      .glass {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 6px 10px; border-radius: var(--r-pill);
        background: rgba(255,255,255,0.20);
        backdrop-filter: blur(14px) saturate(180%);
        -webkit-backdrop-filter: blur(14px) saturate(180%);
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.45),
          inset 0 -1px 0 rgba(0,0,0,0.18),
          0 1px 6px rgba(0,0,0,0.25);
        color: white; font-family: var(--font);
        font-size: 12px; font-weight: 600; letter-spacing: -0.01em;
      }
      .glass .live {
        width: 6px; height: 6px; border-radius: 50%;
        background: oklch(0.78 0.20 25);
        box-shadow: 0 0 6px oklch(0.78 0.20 25);
      }
      .glass .mono {
        font-family: var(--mono); font-variant-numeric: tabular-nums;
        font-size: 11px; letter-spacing: 0;
      }
      .glass .caps {
        font-family: var(--mono); font-size: 10.5px;
        letter-spacing: 0.08em; text-transform: uppercase;
      }

      /* ====================================================================
         HERO VIDEO — full-bleed clip + 4 glass overlays + play button
         ==================================================================== */
      .hero {
        position: relative; width: 100%; overflow: hidden;
        background: #1A1A1A;
        background-size: cover; background-position: center 22%;
      }
      .hero video {
        display: block; width: 100%; height: 100%;
        object-fit: cover;
        background: #1A1A1A;
      }
      .hero .overlay-top, .hero .overlay-bot {
        position: absolute; left: 10px; right: 10px;
        display: flex; justify-content: space-between; gap: 8px;
        z-index: 3; pointer-events: none;
      }
      .hero .overlay-top { top: 10px; align-items: flex-start; }
      .hero .overlay-bot { bottom: 10px; align-items: flex-end; }
      .hero .play {
        position: absolute; left: 50%; top: 50%;
        transform: translate(-50%,-50%);
        width: 56px; height: 56px; border-radius: 50%;
        background: rgba(255,255,255,0.20);
        backdrop-filter: blur(16px) saturate(180%);
        -webkit-backdrop-filter: blur(16px) saturate(180%);
        border: none; outline: none;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.5),
          inset 0 -1px 0 rgba(0,0,0,0.25),
          0 6px 18px rgba(0,0,0,0.35);
        display: grid; place-items: center;
        color: white; font-size: 22px; padding-left: 4px;
        z-index: 5; cursor: pointer;
        transition: transform 120ms ease, filter 120ms ease;
      }
      .hero .play:hover { transform: translate(-50%,-50%) scale(1.06); filter: brightness(1.1); }
      .hero .play:active { transform: translate(-50%,-50%) scale(0.96); }
      .hero.no-play .play { display: none; }

      /* ====================================================================
         POP-OUT VIDEO MODAL — appended to <body> by the binder script
         ==================================================================== */
      .artemis-modal {
        position: fixed; inset: 0; z-index: 99999;
        display: grid; place-items: center;
        animation: artemis-modal-in 180ms ease-out;
      }
      @keyframes artemis-modal-in {
        from { opacity: 0; }
        to   { opacity: 1; }
      }
      .artemis-modal-backdrop {
        position: absolute; inset: 0;
        background: rgba(10,10,8,0.88);
        backdrop-filter: blur(18px) saturate(160%);
        -webkit-backdrop-filter: blur(18px) saturate(160%);
        cursor: zoom-out;
      }
      .artemis-modal-frame {
        position: relative;
        max-width: min(96vw, 1400px);
        max-height: 94vh;
        display: flex; align-items: center; justify-content: center;
        animation: artemis-modal-pop 240ms cubic-bezier(0.2, 0.9, 0.3, 1.2);
      }
      @keyframes artemis-modal-pop {
        from { transform: scale(0.92); opacity: 0; }
        to   { transform: scale(1);    opacity: 1; }
      }
      .artemis-modal-video {
        max-width: 96vw; max-height: 94vh;
        width: auto; height: auto;
        object-fit: contain; background: #000;
        border-radius: 18px;
        box-shadow:
          0 30px 80px rgba(0,0,0,0.55),
          0 2px 6px rgba(0,0,0,0.4),
          inset 0 1px 0 rgba(255,255,255,0.08);
      }
      .artemis-modal-close {
        position: absolute; top: -14px; right: -14px;
        width: 40px; height: 40px; border-radius: 50%;
        border: none; cursor: pointer;
        background: linear-gradient(180deg, #FFFFFF, #EFEDE8);
        color: var(--ink); font-size: 22px; line-height: 1; font-weight: 400;
        display: grid; place-items: center;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.7),
          inset 0 -1px 0 rgba(0,0,0,0.10),
          0 6px 18px rgba(0,0,0,0.4);
        transition: transform 120ms ease, filter 120ms ease;
        z-index: 2;
      }
      .artemis-modal-close:hover { filter: brightness(0.97); transform: scale(1.06); }
      .artemis-modal-close:active { transform: scale(0.94); }
      @media (max-width: 520px) {
        .artemis-modal-close { top: 8px; right: 8px; }
      }

      /* ====================================================================
         CARDS
         ==================================================================== */
      .card {
        background: var(--surface);
        border: 1px solid var(--hairline);
        border-radius: var(--r-card-lg);
        box-shadow: var(--shadow-card);
        overflow: hidden;
        margin-bottom: 14px;
      }
      .card-lg { border-radius: 18px; }
      .card-md { border-radius: 16px; }

      .card-head {
        display: flex; align-items: center; gap: 10px;
        padding: 12px 14px 10px;
      }
      .card-head .meta { flex: 1; min-width: 0; }
      .card-head .name {
        font-family: var(--font); font-size: 14px; font-weight: 700;
        color: var(--ink); letter-spacing: -0.01em; line-height: 1.15;
      }
      .card-head .sub {
        font-family: var(--font); font-size: 11.5px; font-weight: 500;
        color: var(--muted); margin-top: 1px;
      }

      .card-title {
        padding: 0 14px 6px;
        font-family: var(--font); font-size: 16px; font-weight: 700;
        color: var(--ink); letter-spacing: -0.02em; line-height: 1.2;
      }
      .card-chips {
        padding: 0 14px 10px;
        display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
      }
      .card-foot {
        display: flex; align-items: center; gap: 16px;
        padding: 10px 14px;
        border-top: 1px solid var(--hairline);
        font-family: var(--font); font-size: 12px; font-weight: 600;
        color: var(--muted);
      }
      .card-foot .open {
        margin-left: auto; color: var(--amber-deep); font-weight: 700;
      }

      /* Amber hero panel (today's leaderboard, this-week summary, grade preview) */
      .amber-panel {
        background: linear-gradient(135deg, #FFF5E5 0%, #FFE7C7 100%);
        border-radius: 18px; padding: 14px;
        border: 1px solid var(--hairline);
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.6),
          0 1px 2px rgba(0,0,0,0.04);
        position: relative; overflow: hidden;
      }
      .amber-panel .eyebrow {
        font-family: var(--font); font-size: 9.5px; font-weight: 800;
        letter-spacing: 0.12em; text-transform: uppercase;
        color: var(--amber-deep);
      }
      .amber-panel .title {
        font-family: var(--font); font-size: 18px; font-weight: 800;
        letter-spacing: -0.02em; color: var(--ink); margin-top: 4px;
      }
      .amber-panel .ava-stack {
        display: flex; align-items: center; margin-top: 10px;
      }
      .amber-panel .ava-stack .ava { border: 2px solid rgba(255,255,255,0.75); }
      .amber-panel .ava-stack .ava + .ava { margin-left: -8px; }
      .amber-panel .ava-stack .more {
        margin-left: 10px;
        font-family: var(--mono); font-variant-numeric: tabular-nums;
        font-size: 11px; font-weight: 600; color: var(--ink-2);
      }

      /* ====================================================================
         STAT ROW / STAT GRID
         ==================================================================== */
      .stat-row {
        display: grid; grid-template-columns: repeat(4, 1fr);
        border-top: 1px solid var(--hairline);
      }
      .stat-row .tile {
        padding: 10px 12px;
        border-right: 1px solid var(--hairline);
      }
      .stat-row .tile:last-child { border-right: none; }

      .stat-grid {
        display: grid; grid-template-columns: repeat(3, 1fr);
        background: var(--surface);
        border: 1px solid var(--hairline);
        border-radius: 16px;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.6),
          0 1px 2px rgba(0,0,0,0.04);
        overflow: hidden;
      }
      .stat-grid .tile { padding: 14px 12px; }
      .stat-grid .tile:not(:nth-child(3n)) { border-right: 1px solid var(--hairline); }
      .stat-grid .tile:nth-child(n+4) { border-top: 1px solid var(--hairline); }

      .stat-tile { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
      .stat-tile .value {
        font-family: var(--mono); font-weight: 600;
        font-size: 24px; color: var(--ink);
        letter-spacing: -0.04em; line-height: 1;
        font-variant-numeric: tabular-nums;
        display: flex; align-items: baseline; gap: 2px;
      }
      .stat-tile .value .u {
        font-size: 11px; color: var(--muted); font-weight: 500;
      }
      .stat-tile .label {
        font-family: var(--font); font-size: 9.5px; font-weight: 700;
        letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted);
      }
      .stat-tile.big .value { font-size: 34px; }
      .stat-tile.big .value .u { font-size: 14px; }

      @media (max-width: 520px) {
        .stat-row { grid-template-columns: repeat(2, 1fr); }
        .stat-row .tile {
          border-right: 1px solid var(--hairline);
          border-bottom: 1px solid var(--hairline);
        }
        .stat-row .tile:nth-child(2n) { border-right: none; }
        .stat-row .tile:nth-last-child(-n+2) { border-bottom: none; }
      }

      /* ====================================================================
         FILTER PILL ROW (feed)
         ==================================================================== */
      .filter-row {
        display: flex; gap: 6px; padding: 4px 0 4px;
        overflow-x: auto; scrollbar-width: none;
      }
      .filter-row::-webkit-scrollbar { display: none; }
      .filter-row .fp {
        padding: 6px 12px; border-radius: var(--r-pill);
        background: transparent; border: 1px solid transparent;
        font-family: var(--font); font-size: 12px; font-weight: 700;
        color: var(--muted); white-space: nowrap;
        display: inline-flex; align-items: center; gap: 6px;
      }
      .filter-row .fp.on {
        background: linear-gradient(180deg, #FFFFFF, #EFEDE8);
        border-color: var(--hairline);
        color: var(--ink);
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.7),
          0 1px 2px rgba(0,0,0,0.04);
      }
      .filter-row .fp .n {
        font-family: var(--mono); font-size: 10px;
        color: var(--muted); font-weight: 600;
      }
      .filter-row .fp.on .n { color: var(--amber-deep); }

      /* ====================================================================
         GRADE PYRAMID
         ==================================================================== */
      .pyramid { padding: 10px 14px; }
      .pyramid .row {
        display: grid; grid-template-columns: 80px 1fr 36px;
        align-items: center; gap: 10px; padding: 4px 0;
      }
      .pyramid .label {
        display: flex; align-items: center; gap: 8px;
        font-family: var(--font); font-size: 11.5px; font-weight: 700;
        color: var(--ink-2);
      }
      .pyramid .bar {
        height: 10px; border-radius: var(--r-pill);
        background: rgba(20,20,18,0.05); overflow: hidden;
        box-shadow: inset 0 1px 0 rgba(0,0,0,0.06);
      }
      .pyramid .fill {
        height: 100%;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.5);
        border-radius: var(--r-pill);
      }
      .pyramid .n {
        font-family: var(--mono); font-size: 11px; text-align: right;
        color: var(--ink); font-weight: 600;
        font-variant-numeric: tabular-nums;
      }

      /* ====================================================================
         RECENT-CLIMBS list rows
         ==================================================================== */
      .row-list { background: var(--surface); border: 1px solid var(--hairline);
        border-radius: 16px; overflow: hidden;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.6),
          0 1px 2px rgba(0,0,0,0.04);
      }
      .row-list .row {
        display: flex; align-items: center; gap: 10px;
        padding: 12px 14px;
        border-top: 1px solid var(--hairline);
      }
      .row-list .row:first-child { border-top: none; }
      .row-list .row .body { flex: 1; min-width: 0; }
      .row-list .row .body .t {
        font-family: var(--font); font-size: 13px; font-weight: 700;
        letter-spacing: -0.01em; color: var(--ink);
      }
      .row-list .row .body .s {
        font-family: var(--font); font-size: 11px; font-weight: 500;
        color: var(--muted);
      }
      .row-list .row .time {
        font-family: var(--mono); font-variant-numeric: tabular-nums;
        font-size: 13px; font-weight: 600; letter-spacing: -0.02em;
      }

      /* ====================================================================
         FORM ROWS (upload)
         ==================================================================== */
      .form-card { background: var(--surface); border: 1px solid var(--hairline);
        border-radius: 16px; overflow: hidden;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.6),
          0 1px 2px rgba(0,0,0,0.04);
      }
      .form-row {
        display: flex; align-items: center; gap: 10px;
        padding: 12px 14px;
        border-top: 1px solid var(--hairline);
      }
      .form-row:first-child { border-top: none; }
      .form-row .label {
        width: 88px; flex-shrink: 0;
        font-family: var(--font); font-size: 10px; font-weight: 800;
        letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted);
      }
      .form-row .value {
        flex: 1; font-family: var(--font); font-size: 14px; font-weight: 600;
        color: var(--ink); letter-spacing: -0.01em;
      }

      .dropzone {
        background: var(--surface); border-radius: 18px;
        border: 1.5px dashed var(--amber);
        padding: 28px 18px; text-align: center;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.6),
          0 1px 2px rgba(244,122,0,0.06);
      }
      .dropzone .icon {
        width: 56px; height: 56px; border-radius: 18px; margin: 0 auto 12px;
        background: linear-gradient(180deg, var(--amber-soft), var(--amber-deep));
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.5),
          0 4px 14px var(--amber-glow);
        display: grid; place-items: center; color: white; font-size: 26px;
      }
      .dropzone .t {
        font-family: var(--font); font-weight: 800; font-size: 16px;
        letter-spacing: -0.02em; margin-bottom: 4px;
      }
      .dropzone .s {
        font-family: var(--font); font-size: 12px; color: var(--muted);
        font-weight: 600;
      }

      /* ====================================================================
         Streamlit primitive restyling
         ==================================================================== */
      /* Page H1 */
      .page-h1 {
        font-family: var(--font); font-size: clamp(24px, 6vw, 26px);
        font-weight: 800; letter-spacing: -0.03em; line-height: 1.1;
        color: var(--ink); margin: 0 0 6px;
      }
      .page-sub {
        font-family: var(--font); font-size: 13px; color: var(--muted);
        font-weight: 500; margin: 0 0 16px;
      }

      /* Streamlit container -> card */
      [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surface) !important;
        border: 1px solid var(--hairline) !important;
        border-radius: var(--r-card-lg) !important;
        margin-bottom: 14px !important;
        padding: 0 !important;
        box-shadow: var(--shadow-card);
        overflow: hidden;
      }
      [data-testid="stVerticalBlockBorderWrapper"] > div > div {
        padding: 0 !important; gap: 0 !important;
      }

      /* Buttons */
      .stButton > button {
        border-radius: var(--r-pill) !important;
        font-family: var(--font) !important;
        font-weight: 700 !important;
        font-size: 11.5px !important;
        letter-spacing: 0.04em !important;
        text-transform: uppercase !important;
        padding: 6px 14px !important;
        min-height: 32px !important;
        height: 32px !important;
        white-space: nowrap !important;
        background: linear-gradient(180deg, #FFFFFF, #EFEDE8) !important;
        color: var(--ink) !important;
        border: 1px solid var(--hairline) !important;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.55),
          inset 0 -1px 0 rgba(0,0,0,0.10),
          0 1px 2px rgba(0,0,0,0.05) !important;
        transition: filter 120ms ease, transform 80ms ease !important;
      }
      .stButton > button:hover {
        filter: brightness(0.97);
        transform: translateY(-1px);
      }
      .stButton > button[kind="primary"] {
        color: white !important;
        background: linear-gradient(180deg, var(--amber-soft), var(--amber-deep)) !important;
        border: none !important;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.55),
          inset 0 -1px 0 rgba(0,0,0,0.10),
          0 1px 2px var(--amber-glow) !important;
        text-shadow: 0 1px 0 rgba(160,70,0,0.18);
      }
      .stButton > button[kind="primary"]:hover { filter: brightness(1.04); }
      .stButton > button:focus-visible {
        outline: 3px solid rgba(244, 122, 0, 0.4) !important;
        outline-offset: 2px !important;
      }

      /* CTA button (analyze climb) — full width, larger amber pill */
      .cta-full .stButton > button,
      .cta-full .stFormSubmitButton > button {
        width: 100% !important;
        min-height: 48px !important;
        height: 48px !important;
        font-size: 14px !important;
        border-radius: 14px !important;
        background: linear-gradient(180deg, var(--amber-soft), var(--amber-deep)) !important;
        color: white !important;
        border: none !important;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.5),
          inset 0 -1px 0 rgba(0,0,0,0.12),
          0 4px 14px var(--amber-glow) !important;
      }

      /* nav-active wraps a Streamlit button to style it as a selected white pill */
      .nav-active .stButton > button {
        background: linear-gradient(180deg, #FFFFFF, #EFEDE8) !important;
        color: var(--ink) !important;
        border: 1px solid var(--hairline) !important;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.7),
          inset 0 -1px 0 rgba(0,0,0,0.08),
          0 1px 2px rgba(0,0,0,0.06) !important;
        opacity: 1 !important;
      }
      .nav-active .stButton > button:disabled,
      .nav-active .stButton > button[disabled] {
        opacity: 1 !important; color: var(--ink) !important;
      }
      .nav-amber .stButton > button {
        background: linear-gradient(180deg, var(--amber-soft), var(--amber-deep)) !important;
        color: white !important;
        border: none !important;
        text-transform: uppercase !important;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.55),
          inset 0 -1px 0 rgba(0,0,0,0.10),
          0 1px 2px var(--amber-glow) !important;
      }

      /* back link button */
      .back-link .stButton > button {
        background: transparent !important;
        border: none !important;
        color: var(--muted) !important;
        text-transform: none !important;
        letter-spacing: -0.01em !important;
        padding: 6px 0 !important;
        min-height: 28px !important;
        height: 28px !important;
        font-weight: 700 !important;
        font-size: 13px !important;
        box-shadow: none !important;
      }
      .back-link .stButton > button:hover {
        color: var(--ink) !important; filter: none;
        transform: none !important;
      }

      /* Inputs */
      .stTextInput input, .stSelectbox > div > div,
      [data-testid="stFileUploader"] section {
        border-radius: 12px !important;
        border-color: var(--hairline) !important;
        font-family: var(--font) !important;
      }
      .stTextInput input {
        font-weight: 600 !important;
        color: var(--ink) !important;
        background: var(--surface) !important;
      }
      .stTextInput input:focus,
      .stSelectbox > div > div:focus-within {
        border-color: var(--amber-deep) !important;
        box-shadow: 0 0 0 3px rgba(244, 122, 0, 0.18) !important;
      }
      .stTextInput label, .stSelectbox label,
      [data-testid="stFileUploader"] label,
      [data-testid="stWidgetLabel"] {
        font-family: var(--font) !important;
        font-size: 10px !important;
        font-weight: 800 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        color: var(--muted) !important;
      }
      [data-testid="stRadio"] label { text-transform: none !important; letter-spacing: 0 !important; }
      [data-testid="stRadio"] > label { font-size: 10px !important; font-weight: 800 !important; text-transform: uppercase !important; }
      [data-testid="stFileUploader"] section {
        background: var(--surface-tint) !important;
        border: 1.5px dashed var(--amber) !important;
      }

      /* Forms wrapper */
      [data-testid="stForm"] {
        background: var(--surface) !important;
        border: 1px solid var(--hairline) !important;
        border-radius: var(--r-card-lg) !important;
        padding: var(--s-4) var(--card-pad-x) !important;
        box-shadow: var(--shadow-card);
      }

      /* st.video inside our card */
      [data-testid="stVideo"] video {
        border-radius: 0 !important;
        display: block; width: 100%; background: #000;
      }
      [data-testid="stVideo"] { margin: 0 !important; }

      /* expander tweaks */
      [data-testid="stExpander"] {
        border: 1px solid var(--hairline) !important;
        border-radius: 16px !important;
        background: var(--surface) !important;
        box-shadow: var(--shadow-card);
      }

      /* Movement timeline + toggles */
      .timeline-card { padding: 14px; }
      .timeline-x {
        display: flex; justify-content: space-between;
        font-family: var(--mono); font-size: 10px; color: var(--muted);
        margin-top: 8px; font-variant-numeric: tabular-nums;
      }
      .move-chips { display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap; }
      .move-chips .at {
        font-family: var(--mono); font-size: 10px; font-weight: 600;
        color: var(--muted); font-variant-numeric: tabular-nums;
        align-self: center;
      }

      .toggle-row {
        display: flex; align-items: center; gap: 10px; padding: 4px 0;
      }
      .toggle {
        width: 32px; height: 18px; border-radius: var(--r-pill);
        position: relative; background: rgba(20,20,18,0.10);
        box-shadow: inset 0 1px 1px rgba(0,0,0,0.08);
      }
      .toggle.on {
        background: linear-gradient(180deg, var(--amber-soft), var(--amber-deep));
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.4),
          0 1px 2px rgba(244,122,0,0.3);
      }
      .toggle .knob {
        position: absolute; top: 2px; left: 2px;
        width: 14px; height: 14px; border-radius: 50%; background: white;
        box-shadow: 0 1px 2px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.8);
        transition: left 0.2s;
      }
      .toggle.on .knob { left: 16px; }
      .toggle-label {
        font-family: var(--font); font-size: 12.5px; font-weight: 600;
        color: var(--ink); letter-spacing: -0.01em;
      }

      /* Streamlit "info" / "warning" / "error" boxes — softer in the new system */
      [data-testid="stAlert"] {
        border-radius: 16px !important;
        border: 1px solid var(--hairline) !important;
        box-shadow: var(--shadow-card);
      }

      /* ====================================================================
         HACKER NEWS-STYLE RANKED FEED
         ==================================================================== */
      .hn {
        background: var(--surface);
        border: 1px solid var(--hairline);
        border-radius: var(--r-card-lg);
        box-shadow: var(--shadow-card);
        overflow: hidden;
      }
      .hn-row {
        display: grid;
        grid-template-columns: 28px 16px 1fr auto;
        align-items: baseline;
        gap: 10px;
        padding: 10px 14px;
        border-top: 1px solid var(--hairline);
        text-decoration: none;
        color: inherit;
      }
      .hn-row:first-child { border-top: none; }
      .hn-row:hover { background: var(--surface-tint); }
      .hn-row .rank {
        font-family: var(--mono); font-variant-numeric: tabular-nums;
        font-size: 13px; font-weight: 700; color: var(--muted);
        text-align: right; line-height: 1.2;
      }
      .hn-row.top1 .rank, .hn-row.top2 .rank, .hn-row.top3 .rank { color: var(--amber-deep); }
      .hn-row .chip { margin-top: 4px; }
      .hn-row .title {
        font-family: var(--font); font-size: 13.5px; font-weight: 700;
        color: var(--ink); letter-spacing: -0.01em; line-height: 1.3;
      }
      .hn-row .title .grade-inline {
        font-family: var(--font); font-size: 10.5px; font-weight: 700;
        color: var(--muted); letter-spacing: 0.06em; text-transform: uppercase;
        margin-left: 6px;
      }
      .hn-row .meta {
        font-family: var(--font); font-size: 11.5px; font-weight: 500;
        color: var(--muted); margin-top: 2px; line-height: 1.4;
      }
      .hn-row .meta .who { color: var(--ink-2); font-weight: 600; }
      .hn-row .meta .mono {
        font-family: var(--mono); font-variant-numeric: tabular-nums;
        font-weight: 600; color: var(--ink-2);
      }
      .hn-row .meta .pts { color: var(--amber-deep); font-weight: 700; }
      .hn-row .right {
        display: flex; align-items: center; gap: 8px;
      }
      .hn-row .right .t {
        font-family: var(--mono); font-variant-numeric: tabular-nums;
        font-size: 12.5px; font-weight: 700; color: var(--ink);
        letter-spacing: -0.02em;
      }

      /* Like button (heart) — used in feed cards, HN list, post detail */
      .like {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 3px 10px 3px 8px; border-radius: var(--r-pill);
        background: linear-gradient(180deg, #FFFFFF, #EFEDE8);
        border: 1px solid var(--hairline);
        color: var(--ink-2); text-decoration: none;
        font-family: var(--font); font-size: 12px; font-weight: 700;
        letter-spacing: -0.01em;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.55),
          0 1px 2px rgba(0,0,0,0.05);
        transition: transform 80ms ease, filter 120ms ease;
      }
      .like:hover { filter: brightness(0.97); transform: translateY(-1px); }
      .like .heart { font-size: 13px; line-height: 1; color: var(--muted); }
      .like .n {
        font-family: var(--mono); font-variant-numeric: tabular-nums;
        font-size: 12px; color: var(--ink); font-weight: 600;
      }
      .like.on {
        background: linear-gradient(180deg, oklch(0.96 0.08 25), oklch(0.88 0.16 25));
        border-color: transparent; color: white;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.55),
          inset 0 -1px 0 rgba(0,0,0,0.10),
          0 1px 2px rgba(215,38,61,0.35);
      }
      .like.on .heart { color: white; }
      .like.on .n { color: white; }

      /* ====================================================================
         LEADERBOARDS — podium + per-route boards
         ==================================================================== */
      .podium-wrap {
        background: linear-gradient(135deg, #FFF5E5 0%, #FFE7C7 100%);
        border: 1px solid var(--hairline);
        border-radius: 22px;
        padding: 18px 16px 22px;
        margin-bottom: 18px;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.6),
          0 1px 2px rgba(0,0,0,0.04),
          0 12px 30px rgba(244,122,0,0.10);
      }
      .podium-wrap .eyebrow {
        font-family: var(--font); font-size: 9.5px; font-weight: 800;
        letter-spacing: 0.12em; text-transform: uppercase;
        color: var(--amber-deep); text-align: center;
      }
      .podium-wrap .super-title {
        font-family: var(--font); font-size: 22px; font-weight: 800;
        letter-spacing: -0.025em; color: var(--ink);
        text-align: center; margin: 4px 0 18px;
      }
      .podium-row {
        display: grid; grid-template-columns: 1fr 1.15fr 1fr;
        gap: 10px; align-items: end;
      }
      @media (max-width: 520px) {
        .podium-row { grid-template-columns: 1fr 1.15fr 1fr; gap: 6px; }
      }
      .podium-col {
        display: flex; flex-direction: column; align-items: center;
        gap: 6px; padding: 14px 8px 12px;
        background: rgba(255,255,255,0.65);
        border: 1px solid var(--hairline);
        border-radius: 16px;
        text-decoration: none; color: inherit;
        backdrop-filter: blur(8px) saturate(140%);
        -webkit-backdrop-filter: blur(8px) saturate(140%);
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.7),
          0 1px 2px rgba(0,0,0,0.04);
        transition: transform 120ms ease, filter 120ms ease;
        min-width: 0;
      }
      .podium-col:hover { transform: translateY(-2px); filter: brightness(1.02); }
      .podium-col.rank-1 {
        padding-top: 22px; padding-bottom: 18px;
        background: linear-gradient(180deg, #FFFFFF, #FFF1DA);
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.8),
          0 6px 20px rgba(244,122,0,0.25),
          0 1px 2px rgba(0,0,0,0.04);
      }
      .podium-col.empty {
        color: var(--muted); justify-content: center;
        font-family: var(--mono); font-size: 22px;
        opacity: 0.55; min-height: 150px;
      }
      .podium-col .medal { font-size: 22px; line-height: 1; }
      .podium-col.rank-1 .medal { font-size: 30px; }
      .podium-col .name {
        font-family: var(--font); font-size: 12.5px; font-weight: 700;
        letter-spacing: -0.01em; color: var(--ink); text-align: center;
        max-width: 100%; overflow: hidden; text-overflow: ellipsis;
        white-space: nowrap;
      }
      .podium-col.rank-1 .name { font-size: 14px; font-weight: 800; }
      .podium-col .time {
        font-family: var(--mono); font-variant-numeric: tabular-nums;
        font-size: 22px; font-weight: 600; letter-spacing: -0.04em;
        color: var(--ink); line-height: 1;
        display: inline-flex; align-items: baseline; gap: 2px;
      }
      .podium-col.rank-1 .time { font-size: 30px; color: var(--amber-deep); }
      .podium-col .time .u { font-size: 12px; color: var(--muted); font-weight: 500; }
      .podium-col.rank-1 .time .u { font-size: 14px; }
      .podium-col .grade-row {
        display: inline-flex; align-items: center; gap: 6px;
        font-family: var(--font); font-size: 10.5px; font-weight: 700;
        color: var(--muted); letter-spacing: 0.04em; text-transform: uppercase;
      }

      /* Per-route leaderboard card */
      .lb-card {
        background: var(--surface); border: 1px solid var(--hairline);
        border-radius: var(--r-card-lg);
        box-shadow: var(--shadow-card);
        padding: 14px 14px 8px; margin-bottom: 14px;
      }
      .lb-card .head {
        display: flex; align-items: center; gap: 10px; margin-bottom: 10px;
      }
      .lb-card .head .title {
        font-family: var(--font); font-size: 14px; font-weight: 800;
        letter-spacing: -0.02em; color: var(--ink);
      }
      .lb-card .head .label {
        font-family: var(--font); font-size: 9.5px; font-weight: 700;
        color: var(--muted); letter-spacing: 0.1em; text-transform: uppercase;
      }
      .lb-card .head .right {
        margin-left: auto;
        font-family: var(--font); font-size: 10px; font-weight: 700;
        color: var(--muted); letter-spacing: 0.1em; text-transform: uppercase;
      }
      .lb-row {
        display: grid; grid-template-columns: 22px 28px 1fr auto;
        align-items: center; gap: 10px;
        padding: 8px 4px;
        border-top: 1px solid var(--hairline);
        text-decoration: none; color: inherit;
      }
      .lb-row:first-of-type { border-top: none; }
      .lb-row:hover { background: var(--surface-tint); }
      .lb-row .rank {
        font-family: var(--mono); font-variant-numeric: tabular-nums;
        font-size: 12px; font-weight: 700; color: var(--muted);
        text-align: right;
      }
      .lb-row.top1 .rank, .lb-row.top2 .rank, .lb-row.top3 .rank { color: var(--amber-deep); }
      .lb-row .who {
        font-family: var(--font); font-size: 12.5px; font-weight: 700;
        letter-spacing: -0.01em; color: var(--ink);
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .lb-row .who .last { color: var(--muted); font-weight: 500; margin-left: 4px; }
      .lb-row .t {
        font-family: var(--mono); font-variant-numeric: tabular-nums;
        font-size: 13px; font-weight: 700; color: var(--ink);
        letter-spacing: -0.02em;
      }

      /* Climber picker grid (profile, no id) */
      .climbers-grid {
        display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: 12px;
      }
      .climber-tile {
        background: var(--surface); border: 1px solid var(--hairline);
        border-radius: 16px; padding: 14px;
        display: flex; align-items: center; gap: 12px;
        text-decoration: none; color: inherit;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.6),
          0 1px 2px rgba(0,0,0,0.04);
        transition: transform 120ms ease, filter 120ms ease;
      }
      .climber-tile:hover { transform: translateY(-2px); filter: brightness(1.02); }
      .climber-tile .meta { flex: 1; min-width: 0; }
      .climber-tile .meta .n {
        font-family: var(--font); font-size: 14px; font-weight: 700;
        color: var(--ink); letter-spacing: -0.01em;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .climber-tile .meta .s {
        font-family: var(--font); font-size: 11.5px; font-weight: 500;
        color: var(--muted); margin-top: 2px;
      }
      .climber-tile .pin {
        font-family: var(--mono); font-variant-numeric: tabular-nums;
        font-size: 13px; font-weight: 700; color: var(--amber-deep);
      }

      /* Segmented toggle (cards / list) */
      .seg {
        display: inline-flex; padding: 3px; gap: 3px;
        background: rgba(20,20,18,0.05);
        border-radius: var(--r-pill);
        border: 1px solid var(--hairline);
      }
      .seg a {
        display: inline-flex; align-items: center;
        padding: 5px 12px; border-radius: var(--r-pill);
        font-family: var(--font); font-size: 11.5px; font-weight: 700;
        letter-spacing: 0.04em; text-transform: uppercase;
        color: var(--muted); text-decoration: none;
      }
      .seg a.on {
        background: linear-gradient(180deg, #FFFFFF, #EFEDE8);
        color: var(--ink);
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.7),
          0 1px 2px rgba(0,0,0,0.06);
      }

      /* ====================================================================
         CHUMBOX — fake sponsored-content block
         ==================================================================== */
      .chum-card {
        background: #fffbe6;
        border: 1px solid #f0d878;
        border-radius: 10px;
        padding: 6px 8px 4px;
        margin: 0 0 var(--s-3);
        font-family: Georgia, "Times New Roman", serif;
      }
      .chum-label {
        font-size: 8.5px; font-weight: 800; letter-spacing: 0.8px;
        text-transform: uppercase; color: #8a6d00;
        margin-bottom: 5px;
      }
      .chum-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 5px;
      }
      @media (max-width: 560px) {
        .chum-grid { grid-template-columns: repeat(4, 1fr); }
      }
      .chum-tile {
        position: relative;
        display: grid;
        background: #fff;
        border: 1px solid #ead27a;
        border-radius: 6px;
        padding: 4px;
        height: 130px;
        contain: layout size;
      }
      .chum-slide {
        grid-area: 1 / 1;
        display: block;
        text-decoration: none;
        color: #1a1a1a;
        opacity: 0;
        pointer-events: none;
        animation: chum-fade 8000ms ease-in-out infinite;
        transition: transform 80ms ease, box-shadow 120ms ease;
      }
      .chum-slide:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 6px rgba(180,140,0,0.25);
      }
      @keyframes chum-fade {
        0%,  45%  { opacity: 1; pointer-events: auto; }
        50%, 95%  { opacity: 0; pointer-events: none; }
        100%      { opacity: 1; pointer-events: auto; }
      }
      @media (prefers-reduced-motion: reduce) {
        .chum-slide { animation: none; }
        .chum-slide:first-child { opacity: 1; pointer-events: auto; }
      }
      .chum-img {
        width: 100%;
        height: 68px;
        background-size: cover;
        background-position: center;
        background-color: #f0e6b0;
        border-radius: 3px;
        margin-bottom: 3px;
        filter: contrast(1.05) saturate(1.15);
      }
      .chum-headline {
        font-size: 10px;
        font-weight: 700;
        line-height: 1.2;
        color: #0033aa;
        text-decoration: underline;
        text-underline-offset: 1px;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
      .chum-src {
        font-size: 8.5px;
        color: #6b6b00;
        margin-top: 2px;
        font-style: italic;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .chum-disclaimer {
        font-size: 8px;
        color: #8a6d00;
        text-align: right;
        margin-top: 3px;
        font-style: italic;
      }

      /* Reduced motion */
      @media (prefers-reduced-motion: reduce) {
        * { transition: none !important; }
        .stButton > button:hover { transform: none !important; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Brand bar — sticky NavBar with wordmark + nav pills + amber CTA
# ---------------------------------------------------------------------------

def _wordmark_html() -> str:
    if _WORDMARK_URI:
        return (
            f'<div class="artemis-mark">'
            f'<img src="{_WORDMARK_URI}" alt="artemis">'
            f'</div>'
        )
    return (
        '<div class="artemis-mark">'
        '<div style="font-family: var(--font); font-size: 22px; font-weight: 800;'
        ' letter-spacing: -0.04em; color: var(--amber-deep);">artemis</div>'
        '</div>'
    )


_NAV_ITEMS = [
    ("feed", "feed", "feed"),
    ("leaderboards", "boards", "boards"),
    ("profile", "profile", "profile"),
]


def _nav_holds_html(active_view: str) -> str:
    """Render the three climbing-hold nav buttons as image anchors."""
    items: list[str] = []
    for target_view, alt, label in _NAV_ITEMS:
        uri = _NAV_URIS.get(target_view, "")
        if not uri:
            continue
        on_cls = " on" if active_view == target_view else ""
        href = f"?view={target_view}" if target_view != "feed" else "?view=feed"
        items.append(
            f'<a class="nav-hold{on_cls}" href="{href}" target="_self" aria-label="{label}">'
            f'<img src="{uri}" alt="{alt}">'
            f'</a>'
        )
    return f'<div class="nav-holds">{"".join(items)}</div>'


def _brand_bar() -> None:
    view = st.query_params.get("view", "feed")
    nav_view = view if view in {"feed", "leaderboards", "profile"} else "feed"
    st.markdown("<div class='brand-row'>", unsafe_allow_html=True)
    cols = st.columns([1.4, 2.4, 1.0])
    with cols[0]:
        st.markdown(_wordmark_html(), unsafe_allow_html=True)
    with cols[1]:
        st.markdown(_nav_holds_html(nav_view), unsafe_allow_html=True)
    with cols[2]:
        if view == "upload":
            st.markdown("<div class='nav-active'>", unsafe_allow_html=True)
            st.button(
                "uploading",
                key="brand-upload-here",
                type="secondary",
                use_container_width=True,
                disabled=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='nav-amber'>", unsafe_allow_html=True)
            if st.button(
                "+ upload",
                key="brand-upload",
                type="primary",
                use_container_width=True,
            ):
                st.query_params.clear()
                st.query_params["view"] = "upload"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _session_id() -> str:
    """Return (and lazily create) a stable per-browser session id used as the
    anonymous identity for kudos until real auth lands."""
    sid = st.session_state.get("_session_id")
    if not sid:
        sid = uuid.uuid4().hex
        st.session_state["_session_id"] = sid
    return sid


def _handle_like_param() -> None:
    """If ``?like=N`` is set, toggle a kudo for that attempt against the
    current session, strip the param, and rerun so the page renders at its
    intended URL with the updated count."""
    raw = st.query_params.get("like")
    if not raw:
        return
    try:
        attempt_id = int(raw)
    except (TypeError, ValueError):
        attempt_id = 0
    if attempt_id:
        try:
            queries.toggle_kudos(attempt_id, _session_id())
        except Exception:  # noqa: BLE001 — likes are best-effort, never crash routing.
            pass
    del st.query_params["like"]
    st.rerun()


def main() -> None:
    _handle_like_param()
    _ = _session_id()  # ensure id exists before any view runs
    _brand_bar()
    views.inject_fullscreen_script()
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

    if view == "leaderboards":
        views.leaderboards_view()
        return

    views.feed_view()


if __name__ == "__main__":
    main()
