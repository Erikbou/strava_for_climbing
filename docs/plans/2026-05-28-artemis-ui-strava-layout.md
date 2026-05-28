---
title: Artemis UI — Strava-style layout, density, and accessibility
type: design
date: 2026-05-28
status: draft
---

# Goal

Match **Strava's layout, density, and information hierarchy** while keeping the **Artemis visual identity** (amber gradient, lowercase wordmark, SF Pro Rounded). We want a feed and post page a Strava user would feel at home in within seconds, working from a 360 px mobile viewport up to a centered ~720 px desktop column.

> **Borrow:** structure, spacing scale, stat hierarchy, navigation pattern.
> **Don't borrow:** Strava orange `#FC4C02`, Strava typography, Strava iconography.

---

## 1. What Strava's UI actually does (the layout-level patterns)

Verified from the public marketing site + commonly-known mobile-app patterns; cited specifics noted inline.

### 1.1 Feed card structure (top → bottom)

```
┌────────────────────────────────────────────────┐
│ ●  Climber Name                       4h ago   │  ← 40-44px avatar | name | timestamp
│    Gym • Wall                                  │     14-15px name, 12px secondary
├────────────────────────────────────────────────┤
│ Sent Red · V5-V6                               │  ← 18-20px activity TITLE (climber-set)
│ [color chip] [send/attempt pill]               │     metadata row
├────────────────────────────────────────────────┤
│                                                │
│        [ HIGHLIGHT / OVERLAY THUMBNAIL ]       │  ← 16:9 or portrait hero, edge-to-edge
│                                                │
├────────────────────────────────────────────────┤
│  Time   │ Dynamic │ Smooth.  │ Hang           │  ← BIG-NUMBER stat row, 4 tiles
│  12.4s  │   17    │   78     │  0.8s          │     22-26px values, 10-11px caps labels
├────────────────────────────────────────────────┤
│ ♡ 12   💬 3                          ⤴ Share  │  ← action row (deferred for v1)
└────────────────────────────────────────────────┘
```

**Key observations:**
- **One hero asset per card.** Map/photo on Strava, highlight clip thumbnail for us. Edge-to-edge, no card padding around it.
- **Stats live in a single-row strip at the bottom** with vertical dividers, big bold numbers, ALL-CAPS short labels under each. No icons next to numbers — typography does the work.
- **Title sits *between* header and hero**, never below. The hero supports the title, not the other way around.
- **Tap targets are the whole card** in Strava; we'll keep "view post" as an explicit button per Streamlit constraint.

### 1.2 Activity (post) detail page

```
┌─ back / chrome ───────────────────────────────┐
│                                               │
│ ●●  Climber Name (large avatar)               │
│     4h ago · Gym                              │
│                                               │
│ ╔════════════════════════════════════════════╗│
│ ║   HERO VIDEO (highlight clip)             ║│  ← largest visual element
│ ╚════════════════════════════════════════════╝│
│                                               │
│ Activity Title (h1, 28-32px, weight 800)      │
│ [color chip] V5-V6 — Advanced  [send pill]    │
│                                               │
│ ── stats ──                                   │  ← muted section header
│ ┌──────┬──────┬──────┐                        │
│ │ 12.4s│ 17   │ 78   │                        │   ← 3-col grid, big numbers
│ ├──────┼──────┼──────┤                        │
│ │ 226px│ 0.8s │ 12.4s│                        │
│ └──────┴──────┴──────┘                        │
│                                               │
│ ── full climb · skeleton overlay ──           │
│ [secondary video, demoted below stats]        │
│                                               │
│ ── activity ──   (kudos/comments — deferred)  │
└───────────────────────────────────────────────┘
```

**Key observations:**
- Hero asset comes BEFORE the title in the layout. Strava does this with the map on runs.
- Stats are denser on detail than feed — 2×3 or 2×4 grid with bigger numbers.
- Secondary content (the skeleton overlay) is demoted to a quiet section below the stats — not a tab, but a labelled section.
- Section headers are SMALL ALL-CAPS gray, not big bold. They separate, they don't compete.

### 1.3 Profile page

```
┌─ chrome ──────────────────────────────────────┐
│                                               │
│  ●●●●   Climber Name (h1)                     │  ← 64-80px avatar, name aligned center-left
│         "Indoor boulderer · KCA"              │
│                                               │
│  ┌───────┬─────────┬──────────┐               │
│  │ Sends │ Attempts│ Fastest  │               │   ← summary tile row
│  │  17   │   42    │  8.2s    │               │
│  └───────┴─────────┴──────────┘               │
│                                               │
│  ── recent climbs ──                          │
│  [compact card] [compact card] ...            │
└───────────────────────────────────────────────┘
```

### 1.4 Navigation chrome

Strava mobile uses a **bottom tab bar** with 5 icons (Home, Maps, Record, Groups, You). Our scope is smaller — we have **feed / upload / (post) / profile**. We're already implementing this as a top brand bar with `home` + `+ upload` actions, which is correct for a centered max-720px web demo. **Don't add a bottom tab bar** — it's a phone-native pattern that doesn't transfer cleanly to a web app.

### 1.5 Spacing & density (the "clean as hell" lever)

Strava on mobile:
- **8 px** is the base unit.
- Card vertical rhythm: 16-20 px between major blocks inside a card; 16-20 px between cards.
- **Hairline 1 px dividers** (#ECECEC-ish) between rows inside a stat strip.
- Content respects a **safe-area inset on mobile** (Streamlit handles this with viewport-fit=cover already from our config.toml).

Strava on web:
- **Max content width ~720 px** for the feed, centered.
- More vertical breathing than mobile (24-32 px gaps).

We're already at max-width 720 px. Add a media query for ≤480 px to tighten paddings.

---

## 2. Accessibility audit (current → needed)

| Concern | Current state | Plan |
|---|---|---|
| **Color contrast** | `--muted #6B6B6F` on `--bg #FFF` = 5.4:1 ✓ (passes WCAG AA for normal text). Orange CTA white-on-orange `#ff9a1f` = 2.6:1 ✗ (fails 4.5:1 for body but passes 3:1 for large/UI). | Keep gradient CTA but ensure all body copy uses `--ink #111` or `--muted #6B6B6F`; never use orange for non-CTA text on white. |
| **Keyboard nav** | Streamlit handles tab/enter on buttons. | Add `aria-label` to icon-only buttons (the `↻` reroll, future kudos icon). |
| **Heading order** | Cards currently use `<h1>` inside the post header. Multiple `<h1>` per page is bad for screen readers. | One `<h1>` per page: feed has `<h1>artemis</h1>` brand bar; post page demotes the activity title to `<h1>` and brand to `<div>`. |
| **Focus rings** | `outline: none` is implicitly set by Streamlit's button base. | Re-enable `:focus-visible { outline: 3px solid rgba(244,122,0,0.4); outline-offset: 3px; }` per landing-page pattern. |
| **Reduced motion** | We have a hover scale on buttons. | Wrap any transform/transition in `@media (prefers-reduced-motion: reduce)` guard. |
| **Touch targets** | Buttons are 32 px tall by Streamlit default. WCAG recommends 44×44 px. | Override to `min-height: 44px` for primary buttons, 40 px for secondary. |
| **Alt text on video** | `st.video` doesn't emit useful alt by default. | Add a visually-hidden `<p>` describing the climb above each video tag. |
| **Landmark regions** | Streamlit emits no `<main>` / `<nav>`. | We can't change Streamlit's DOM structure, but we can add `role="main"` via CSS-targeted wrappers in markdown. |

---

## 3. Mobile + desktop strategy in Streamlit

**Constraints we can't change**
- Streamlit renders everything inside its own `<div data-testid="stMain">` chrome.
- No JS for layout — we can only style with CSS.
- `st.columns` is the only horizontal layout primitive; column widths are ratios.
- Buttons are `<button>` inside `<div class="stButton">` and can't be moved into HTML fragments.

**What we can do**
- Inject CSS variables for `--card-padding`, `--gap-major`, `--gap-minor` with responsive overrides.
- Use `clamp()` for all font sizes so they scale with viewport.
- Set `.block-container { padding: clamp(12px, 4vw, 32px); }` so paddings collapse on mobile.
- Use CSS grid for the stat rows (we already do).
- `@media (max-width: 480px)` to: drop avatar from 42 → 36 px, shrink card padding 18 → 14 px, switch the 4-tile stat row to a 2×2 grid.

**Layout plan**
```
mobile (≤480px)            desktop (≥720px)
─────────────────          ────────────────
brand-bar collapses:       brand-bar full row
[wordmark]                 [wordmark]  [home] [+upload]
[home][upload]             

feed card:                 feed card:
[head row 14px pad]        [head row 18px pad]
[title]                    [title]
[hero, 16:9]               [hero, 16:9]
[stat 2x2 grid]            [stat 1x4 row]
[CTA row]                  [CTA row]
```

---

## 4. Concrete change list (ordered by impact)

### Phase 1 — Layout density and hero asset (highest ROI)

1. **Make the highlight clip the hero of feed cards.** Currently it lives on the post page only. Render it inline in `_feed_card` between the title and the stat row, edge-to-edge inside the card border. If the clip doesn't exist, fall back to a still frame (extract one from the normalized video on-demand and cache).
2. **Move the color chip + send badge to the row directly under the title** (currently split across two rows). Single tight line: `[color chip] V5-V6 [send pill]`.
3. **Stat row labels in lowercase 10 px tracked caps** (matches Artemis tagline). Drop "Smoothness" → "smooth" or "flow" to fit four equal columns at 360 px.
4. **Two-column stat row on ≤480 px viewports.** Detect via `@media (max-width: 480px)` and switch `.stat-row { grid-template-columns: repeat(2, 1fr); }`.

### Phase 2 — Activity detail page

5. **Hero highlight clip BEFORE the title** on the post page (currently title comes first, video after stats). Strava's pattern.
6. **2×3 stat grid** on detail (we already have this — verify it looks right with the larger values).
7. **Section headers become labelled muted hairlines**: `── stats ──` with a 1 px line, not just a label. Pure visual cleanup.
8. **Demote the skeleton overlay** to a collapsible section ("Show skeleton overlay" button) so the post isn't overwhelmingly video-heavy.

### Phase 3 — Brand bar + nav

9. **Sticky brand bar** on scroll (CSS `position: sticky; top: 0; backdrop-filter: blur(8px); background: rgba(250,250,250,0.85)`). Strava does this; gives the page a clearer head-of-frame.
10. **Active state on the home/upload buttons** based on `view` query param. Currently `+ upload` disappears when on upload view; make `home` look pressed when on feed.

### Phase 4 — Accessibility pass

11. Add `:focus-visible` outlines (orange-3 ring) on every button + input.
12. Add `aria-label` to icon-only buttons.
13. Single `<h1>` per page — demote brand bar to `<div role="banner">`, page-specific title gets the `<h1>`.
14. Touch targets to 44 px minimum on primary CTAs.
15. `prefers-reduced-motion` media query around button hover/active transitions.

### Phase 5 — Density tweaks

16. Tighten line-height: `1.25` on titles, `1.45` on body.
17. Drop unnecessary divider lines — the card border + the stat-row top border are enough.
18. Reduce profile "recent climbs" cards to a single-line item: chip + grade + send pill + time + open button on ONE row (currently it's two rows of HTML + a button).
19. Compact form: combine climber + color + gym fields into a tighter 2-column layout already; reduce vertical gap.

---

## 5. What NOT to copy from Strava

- **Don't add a bottom tab bar** — Strava's mobile pattern doesn't fit a 720 px web column.
- **Don't add segments, gear, kudos counts, comments** — Leonard's brief explicitly defers the full social graph for v1.
- **Don't use Strava orange `#FC4C02`** — we have our own amber identity.
- **Don't replicate the map** — there's no map in climbing. The hero is the highlight clip.
- **Don't add the activity-type icons** (runner/biker/etc.) — every Artemis activity is a climb.

---

## 6. Implementation order (recommended)

1. Phase 1 first (feed cards become hero-driven) — biggest visual upgrade.
2. Phase 2 second (post detail mirrors the feed hierarchy).
3. Phase 4 accessibility in parallel with Phase 1-2 changes (cheap, mostly CSS).
4. Phase 3 (sticky nav, active states) once layout is settled.
5. Phase 5 density polish last — easiest to ship and iterate on.

Estimated total: **~400 LOC across `main.py` CSS, `views.py` fragments, plus a small `frame_grab.py` helper** for the still-frame fallback. No DB changes. No new dependencies.

---

## 7. Open questions for the team

- **Still-frame fallback for feed hero**: extract via ffmpeg the middle frame of the highlight clip and cache as JPEG? Or just render the video player inline and let users tap to play? (Recommendation: render the player, autoplay muted on hover/scroll-in. Streamlit's `st.video` doesn't support autoplay; we'd need raw HTML `<video autoplay muted loop playsinline>` — Streamlit CSP allows this.)
- **Multi-attempt clips on the feed**: do we collapse same-video attempts into one card with an "N attempts" badge, or keep them as separate posts? Strava posts one activity per workout. (Recommendation: one card per primary attempt; the multi-attempt edge case is rare with current boundary detection.)
- **Empty state for the feed**: keep the current `st.info` block, or add a stronger "upload your first climb" CTA with a sample video link? (Recommendation: keep simple; add the sample video once we have one to ship.)
