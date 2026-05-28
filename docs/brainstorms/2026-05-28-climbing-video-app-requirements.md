# Strava for Climbing — Product Requirements (Brainstorm)

**Date:** 2026-05-28
**Team:** Island Boys (Erik Boustedt, Emil Nobrant, Niklavs Visockis, Leonard Xander)
**Context:** KTH hackathon / course submission
**Status:** High-level scope; technical implementation deferred to planning

---

## Summary

A bouldering app where a climber uploads a video of an indoor climb and the AI returns, on a single result screen, **what route they took, how hard it was, and the best moments of the send** — wrapped in a Strava-style social feed so the experience feels like a real product rather than a notebook demo.

The wow moment is the AI seeing the climb. Everything else is framing.

## Primary Actor

A single climber persona for v1:

- Indoor boulderer at a commercial climbing gym where routes are color-coded.
- Has a phone, films their attempts (their own or with a friend), wants something more interesting than a camera roll afterward.
- Casual-to-intermediate — cares about progress and bragging rights, not yet at the level where dedicated training tools (Crimpd, Kaya) are the right home.

Secondary actors (friends viewing posts in a feed) exist only as light context for the social wrapper.

## Core Outcome

A climber finishes a session, opens the app, uploads one or more clips, and within a short wait gets a post they would actually want to share — auto-labeled with the grade, auto-timed bottom-to-top, with the strongest seconds clipped out as a highlight. They scroll a feed and see other climbers' equivalents.

## Positioning

| Adjacent product | What it does | Why this isn't that |
| --- | --- | --- |
| Strava | Logs runs/rides with GPS, social feed | No GPS to lean on; the unit of activity is a single bouldering attempt, not a route over distance |
| Crimpd / Kaya | Training plans, hangboard timers, send logging | Training-oriented; manual logging; no video understanding |
| 27 Crags / Mountain Project | Outdoor route databases | Outdoor / topo focus; community-curated routes, not AI-inferred from your video |
| Instagram / TikTok with climbing tags | Climbers already post clips | No structured data; no auto-grade, no auto-highlight, no climber-native social signals |

The white space: **video-in, structured-climb-out**, with a social skin that climbers already understand because it borrows Strava's vocabulary.

## In Scope for v1 (Demo)

### Feature 1 — Video to structured climb

Climber uploads a single bouldering video. The app returns:

- **Route taken** — a trace of which holds the climber used, derived from body tracking.
- **Send time** — bottom-to-top duration.
- **A small set of body-derived stats** that feel meaningful to a climber (representative examples: dynamic move count, hang time, longest reach). The exact stat set is an open question — see Open Assumptions.

### Feature 2 — Color-to-grade inference

The app detects the color of the holds the climber actually used and looks that color up in a **hard-coded grade table for one chosen gym**. Output is a grade label on the post.

This intentionally avoids cross-gym generality — every gym uses a different color system. v1 commits to one gym's mapping and treats that as the supported surface.

### Feature 3 — Auto-highlight clip

From the body-tracking signals already produced for Feature 1, the app picks the most interesting seconds of the send and produces a short highlight — examples of "interesting" being moments where the climber covers ground quickly, dynamic moves, or sustained activity after a long pause. The highlight is shareable from the post.

### Strava-style chrome

Just enough to make the AI output feel like a product:

- A feed of posts from other climbers (seeded with team posts during demo).
- A profile screen showing your sends.
- A post detail screen that combines the video, the trace, the grade, the stats, and the highlight clip.

UI borrows Strava's visual language — clean, stat-forward, kudos-style affordance.

## Deferred (Post-Hackathon, If Anyone Keeps Building)

- **Multi-gym color systems.** Pick a second gym, then a third; eventually a gym onboarding flow that lets a gym register its own mapping.
- **Outdoor, sport, lead climbing.** Different scoring system, different filming conditions, different community norms.
- **Real social graph.** Friends, follows, kudos with weight, comments, ranking by grade pyramid.
- **Live / on-wall capture.** Recording inside the app, on-device inference, sensor integration.
- **Auth and onboarding** beyond a stub user.
- **App Store packaging, push notifications, monetization.**

## Outside This Product's Identity

These are not "later" — they are deliberately the wrong product:

- **General fitness tracking.** Strava already owns runs, rides, and steps. Going there is competing on Strava's terms with a worse Strava.
- **Coaching, training plans, hangboard prescriptions.** Crimpd and Kaya territory; pivoting toward it abandons the AI-from-video bet.
- **Route-setting tools for gyms.** A B2B product with different buyers and a different shape entirely.

Naming these matters because each is a tempting "just one more feature" that drifts the product away from its hero moment.

## Success Criteria (Demo-Day)

A judge watching the demo should be able to say, unprompted:

1. *"It actually figured out which holds you used."*
2. *"It correctly identified the grade from the colors."*
3. *"That highlight is the part I would have clipped myself."*
4. *"This feels like an app I would open, not a research notebook."*

Anything beyond those four does not move the demo. Anything that compromises those four is the wrong tradeoff.

## Open Assumptions to Resolve Before Build

These are explicit because each one would silently shape the product if left undecided:

- **Which gym?** A specific Stockholm-area bouldering gym needs to be named so its color-to-grade table can be hard-coded. Filming conditions, hold density, and lighting at that gym become the implicit training environment.
- **Where does demo footage come from?** Team self-recording at the chosen gym is the most controllable source. Existing clips from friends or YouTube introduce variance that may break the demo. This affects how many clips can realistically be processed end-to-end before demo day.
- **Which body-tracking stats earn a place on the post?** "Body tracking" is a category, not a stat. v1 should ship 3–5 stats a climber actually cares about (suggested starting set: send time, dynamic-move count, longest reach, hang time on hardest move, idle/rest seconds) rather than every value the pose model can emit.
- **What does the highlight heuristic actually look at?** The brief says "quick gain of ground" — needs to be a concrete signal (vertical velocity above a threshold, sustained motion after a pause, etc.) chosen during planning.
- **How precise must the grade output be?** Single grade (e.g., "Yellow → V3") versus a range versus a confidence-scored label changes how the model is allowed to fail gracefully on color ambiguity.

## Non-Goals (Sanity Markers)

Stated only because they are easy to drift into:

- No real-time inference. Upload-and-process is fine.
- No cross-device sync, no offline mode.
- No editing tools for the climber to fix the route trace if the model gets it wrong — the AI's output is the output for v1.
- No leaderboard math. A feed is enough.

## Handoff

Next step: planning (`/ce-plan`) to translate the three core features and the Strava-style chrome into a concrete technical approach — model choices, pipeline architecture, UI stack, and a build order that resolves the open assumptions above before they block work.
