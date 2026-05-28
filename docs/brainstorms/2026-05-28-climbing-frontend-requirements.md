---
date: 2026-05-28
topic: climbing-frontend
---

# Strava for Climbing — Frontend v1 Requirements

## Summary

A mobile-first Next.js + Tailwind web app for indoor boulderers: upload a climb video, get a move-by-move analysis (with overlay video and a "who else climbed this" rail), and share it on a Strava-style social feed with follows, kudos, and comments. v1 runs on a mock JSON-file backend with demo-profile sign-in; the social plumbing is real code but the data is seeded, and the ML service plugs in behind a stub endpoint once it lands.

---

## Problem Frame

Climbers already record their attempts on phones, but the videos die in a camera roll. There is no climbing equivalent of opening Strava after a run to see your effort visualized, compare against others on the same segment, and feel the social pull of a feed. For indoor bouldering specifically, "the same problem" is well-defined (a gym + wall + hold color + grade tuple), so the door is open for both per-route leaderboards *and* a social feed — together they give a casual climber a reason to upload every session, not just landmark sends.

The v1 here is the demo-grade frontend that proves the shape end-to-end. The ML model that actually analyzes the video is being built separately and will be slotted in behind a fixed endpoint.

---

## Key Decisions

- **Demo-profile session over real auth.** First visit shows a profile picker; selecting one establishes a cookie-based pseudo-session. Hackathon velocity wins over real auth in v1; the boundary stays clean so NextAuth/Auth.js can replace it later without UI changes.
- **Mock JSON backend over real DB.** Seeded JSON files back the feed, follows, kudos, comments, and routes. Data resets on redeploy and does not cross machines. Social *plumbing* is real code; social *data* is fake. The trade buys ship speed.
- **Move-by-move list as the result hero.** The result page leads with an ordered move timeline; clicking a move scrubs an embedded player below it. The annotated overlay video and the similar-routes rail sit below. Choosing the analytical surface as hero (over a more visceral pose-skeleton overlay) is a coaching-framing bet — the move list is what makes "Strava for climbing" feel like more than a video locker.
- **Hybrid manual + ML route identification.** Climbers tag uploads with gym, wall, color, and grade. v1 treats exact-match on (gym + wall + color) as "the same problem." When the real ML clusterer arrives, it replaces the matcher behind the same surface, no UI change required.
- **Full Strava-style social over leaner variants.** Follows + chronological feed + kudos + comments. The bigger surface earns the "Strava-inspired" framing; mock data carries the demo.
- **Two feed-card shapes.** Video-rich card (with route metadata + ML status badge) for uploads, lightweight text-and-badge card for video-less send logs. Keeps the feed alive without forcing video on every action.
- **Mobile-first responsive.** Designed for a 360px viewport up; desktop is fluid-scaled but not the primary target. Climbers record on phones.
- **Strava-orange palette.** Strava orange (`#FC4C02`) and white as primaries; neutral grays for surfaces and text. Used for primary CTAs, active states, send badges, and brand chrome.

---

## Actors

- A1. **Climber (demo profile)** — the human using the app. Uploads videos, posts send logs, follows others, gives kudos, comments, browses routes.
- A2. **ML analysis service (stub in v1)** — accepts a video reference, returns a fixed-shape JSON payload of move list + overlay URL + similar-routes. Real service drops in behind the same endpoint later.
- A3. **Seeded climber personas** — pre-populated demo accounts with sample climbs, sends, and send-log entries. Make the feed feel alive on first visit.

---

## Requirements

### Identity & demo session

- R1. First visit shows a profile picker with seeded demo climbers; selecting one establishes a cookie-based pseudo-session that persists in that browser.
- R2. A "Create new climber" option lets the user add a fresh profile (display name + avatar) that joins the seeded list for the duration of the session.
- R3. A profile switcher in the nav lets the user swap demo profiles without clearing data.

### Upload & ML analysis

- R4. Authenticated users can upload an MP4/MOV climbing video from device or camera.
- R5. The upload form captures: gym (from a curated list), wall/area (from the gym's walls), hold color, grade (V0–V16), and status (send / flash / attempt / project).
- R6. On submit, the video is sent to a stub `/api/analyze` endpoint that returns a fixed-shape JSON payload: ordered move list with timestamps, overlay-video URL, and a similar-routes array. The real ML replaces the stub later behind the same contract.
- R7. While analysis is pending, the result page shows a loading state with the user's metadata visible; while pending, the activity card in the feed shows an "analyzing…" badge.

### Result page

- R8. The result page renders the move-by-move list as the hero at the top of the page.
- R9. Each move is clickable; clicking a move scrubs the embedded video player to that timestamp.
- R10. The annotated overlay video plays beneath the move list (or as a tabbed view alongside the raw video on wider screens).
- R11. A "similar routes" rail below the analysis links to the per-route page for the (gym, wall, color, grade) tuple of this climb.

### Feed & social

- R12. The home feed renders a vertical chronological list of recent activities from followed climbers and self, newest first.
- R13. Each card supports a kudos toggle (with count) and a comments thread (read existing + post new).
- R14. A user can follow / unfollow any other climber from a profile page; the follow graph is per-session and seeded with a default set on first profile pick.
- R15. The feed surfaces two card types: rich video cards (thumbnail, route metadata, ML status badge, kudos/comments) and lightweight send-log cards (status + grade badge + route metadata + kudos/comments).

### Route discovery

- R16. Each unique (gym, wall, hold color, grade) tuple identifies a route; the result page links to its dedicated page.
- R17. The per-route page lists everyone who has logged a climb on this route, newest first, with their status badges (send / flash / attempt / project) and kudos counts.
- R18. "Similar routes" is implemented in v1 as exact-match on (gym + wall + color). The data surface is shaped so the ML clusterer can replace the matcher later without UI changes.

### Manual send log

- R19. Users can post a video-less "send log" entry capturing the same fields as an upload (gym, wall, color, grade, status) plus an optional one-line note.
- R20. Send logs appear in the feed as lightweight cards, count toward profile stats, and contribute to per-route leaderboards.

### Profile

- R21. Each climber has a profile page showing avatar, display name, total sends, hardest sent grade, a grade pyramid (count of sends per grade), and the climber's recent activities (last 10).
- R22. Other-user profiles render the same surface plus a follow / unfollow button and a "kudos received" count.

### Visual system & form factor

- R23. The UI uses Strava orange (`#FC4C02`) and white as primary brand colors, with neutral grays for surfaces and text. Orange is reserved for primary CTAs, active nav, kudos toggle, and send badges.
- R24. Layouts are mobile-first; every screen is usable at a 360px viewport and scales fluidly to desktop. Primary nav is a bottom tab bar on mobile, top nav on wider viewports.
- R25. The visual language echoes Strava's card-based feed and stat-heavy profile, adapted for climbing (move timelines and grade badges replace pace/elevation).

---

## Key Flows

- F1. **First-visit onboarding**
  - **Trigger:** A new browser session hits the app root.
  - **Actors:** A1, A3
  - **Steps:** Profile picker renders → user selects a seeded persona or creates new → cookie set → land on home feed pre-populated with seed activities from followed personas → empty-state CTA invites the user to upload their first climb.
  - **Covers:** R1, R2, R14, R12

- F2. **Upload + analyze + share**
  - **Trigger:** User taps the upload CTA.
  - **Actors:** A1, A2
  - **Steps:** Pick video (camera or file) → fill metadata form (gym, wall, color, grade, status) → submit → POST to `/api/analyze` (stub) → result page renders with move list hero, overlay video, similar-routes rail → activity appears in the user's feed and own profile.
  - **Covers:** R4–R11, R16

- F3. **Post a video-less send log**
  - **Trigger:** User taps "log a send" (alternate upload entry).
  - **Actors:** A1
  - **Steps:** Form captures gym/wall/color/grade/status + optional note → submit → activity appears in feed as lightweight card and on per-route page.
  - **Covers:** R19, R20, R15

- F4. **Discover others on the same route**
  - **Trigger:** User taps the similar-routes rail or a route badge on any card.
  - **Actors:** A1
  - **Steps:** Per-route page renders → shows ordered list of climbers and their statuses → tap any entry to view that activity or that climber's profile.
  - **Covers:** R16, R17, R18

- F5. **Engage with another climber's activity**
  - **Trigger:** User scrolls feed and pauses on a card.
  - **Actors:** A1
  - **Steps:** Tap kudos → count increments, toggle state persists for session; tap comments → post text → comment appears in thread; tap climber name → land on their profile and optionally follow.
  - **Covers:** R13, R14, R22

---

## Acceptance Examples

- AE1. **Stubbed analysis result**
  - **Covers:** R6, R7, R8, R9
  - **Given** a user submits a valid MP4 with gym/wall/color/grade/status metadata,
  - **When** the stub `/api/analyze` returns its fixed payload after a simulated delay,
  - **Then** the result page renders the move list as hero, the video player is scrubbable from move clicks, the overlay video plays below, and the activity card in the feed transitions from "analyzing…" to its final ML status badge.

- AE2. **Same-route matching in v1**
  - **Covers:** R16, R17, R18
  - **Given** two seeded climbers each logged a climb tagged (Klättercentret Akalla, Slab Wall, Orange, V5),
  - **When** a new user opens the per-route page for that tuple,
  - **Then** both climbers appear ordered newest-first with their respective status badges, and a third climber who logged (Klättercentret Akalla, Slab Wall, *Yellow*, V5) does not appear.

- AE3. **Send log without video**
  - **Covers:** R19, R20
  - **Given** a user posts a send log with no video attached,
  - **When** the feed re-renders,
  - **Then** the entry appears as a lightweight card with grade + status badges, counts toward the user's profile stats, and appears on the relevant per-route page.

- AE4. **Profile picker session boundary**
  - **Covers:** R1, R3
  - **Given** a user is signed in as a seeded profile and has given kudos to a card,
  - **When** the user switches to another seeded profile via the profile switcher,
  - **Then** the feed re-renders from the new profile's perspective, the prior profile's kudos are preserved against that profile, and the new profile's own kudos state is independent.

---

## Scope Boundaries

### Deferred for later

- Real auth (email/password, magic-link, OAuth)
- Real database and persistent storage (Postgres, Supabase, etc.)
- Real ML clusterer for similar-route detection (exact-match stand-in until then)
- Outdoor bouldering, indoor sport / lead, outdoor sport / trad
- Push notifications and email notifications (in-app kudos/comments only in v1)
- Search, hashtags, direct messages
- Native mobile apps
- Production observability, error reporting, analytics, abuse handling

### Outside this product's identity

- A general fitness tracker — this is climbing-specific, not a multi-sport log
- A standalone video-hosting platform — videos exist in service of the analysis + social context, not as the product
- Coaching marketplace / paid features — v1 is single-tier free

---

## Dependencies / Assumptions

- The ML service exposes (or will expose) a JSON contract: input is a video reference, output is `{ moves: [{ timestamp, label, ... }], overlayUrl, similarRoutes: [...] }`. The exact payload shape is finalized when the ML is provided; v1's stub returns a placeholder matching this shape.
- The frontend ships before the ML is ready. v1 uses a fixed mock response so result-page UX is testable end-to-end. When the real ML lands, the stub is swapped behind `/api/analyze`.
- Deployment target is assumed Vercel-friendly (Next.js default). Mock JSON-file persistence has known limits there — see Outstanding Questions.
- No production deadline named beyond "quickly test and deploy" — scope is sized for hackathon-velocity (days, not weeks).
- Seed data (gyms, walls, climbers, climbs, send logs) is hand-authored and committed to the repo as JSON fixtures.

---

## Outstanding Questions

### Resolve before planning

- Where do uploaded video files physically live in v1? Vercel's runtime filesystem is read-only, so options are (a) Vercel Blob, (b) skip persisting the user's video and analyze a fixture instead, (c) accept that uploads only work in local dev. Affects what "upload" really means in the deployed demo.
- Is there a hard demo date? If so, the scope may need cuts (likely candidates: comments thread, per-route leaderboard, profile grade pyramid).
- How many seeded climbers / climbs / gyms make the demo feel alive without becoming a chore to author? Provisional target: 5–8 climbers, 2–3 gyms, ~20 climbs, ~10 send logs.

### Deferred to planning

- Exact ML stub response shape — finalize when the real ML contract is provided.
- Grade pyramid visualization — bar chart vs. tally list vs. heatmap.
- Notifications surface inside the app — bell icon with unread badge, or only inline on cards.
- Whether the camera-capture path (record-in-browser) ships in v1 or only file-pick.
