# Strava for Bouldering — Brainstorm

**Date:** 2026-05-28
**Team:** Island Boys (Erik Boustedt, Emil Nobrant, Niklavs Visockis, Leonard Xander)
**Context:** KTH AI Society hackathon / class project. Greenfield repo. Raw bouldering videos, no labels.

## What We're Building

A "Strava for bouldering" demo that turns raw climbing videos into a **per-route leaderboard** with performance metrics. The wow moment is comparing two climbers' attempts on the same route side-by-side with computed time-to-top, attempt count, and a smoothness score.

Scope is demo-grade on a **curated subset** of the dataset. Not a production app, not a mobile build. End artifact: a pipeline + a simple UI that displays the leaderboard for a handful of routes.

## Why This Approach (Approach B, staged)

Two parallel pipelines layered in two stages:

**Stage 1 (days 1–2): Pose-first MVP.**
Per-frame human pose extraction → tracked trajectory → metrics. Routes grouped by upload metadata or hand-grouping. Always demoable, even if Stage 2 slips.

**Stage 2 (days 3–4): Hold detection + route matching.**
Detect holds, embed the wall layout, cluster videos by route. Makes the leaderboard credible without forcing the user to tag routes.

**Why this over alternatives.** Pose-only (Approach A) ships safely but doesn't honor the explicit interest in auto-route-matching. Full B from day 1 risks running out of time on a brittle CV piece. VLM-only (Approach C) gives wobbly numeric metrics — bad for a leaderboard that needs trustworthy times.

## Key Decisions

- **Demo wow:** performance metrics + per-route leaderboard.
- **Climber identity:** taken from upload metadata, not re-identified from pixels.
- **Route matching:** attempted via CV (Stage 2), with hand-grouped fallback.
- **Curate, don't generalize:** pick ~10–20 videos covering 3–5 routes with the cleanest camera angles. Don't pretend the system handles all gyms.
- **Pretrained only:** no training from scratch. At most a few-hundred-image fine-tune for the hold detector if zero-shot underperforms.
- **No mobile / no user accounts.** Out of scope for the hackathon.

## Open-Source Building Blocks

### Body pose (Stage 1 spine)
- **YOLO11-Pose** (Ultralytics) — easiest API, multi-person, ~real-time. Default choice.
- **RTMPose / RTMW** (OpenMMLab) — more accurate, slightly more setup.
- **MediaPipe Pose / BlazePose** — single-person, mobile-friendly, fallback.
- **ViTPose++** — SOTA accuracy if quality matters more than speed.

### Person tracking
- **ByteTrack** or **BoT-SORT** — both bundled with Ultralytics. Use whichever YOLO ships by default.

### Hold detection (Stage 2)
- **Grounding DINO** + **SAM 2** — zero-shot "climbing hold" prompts → segmentation masks. Best first attempt because it needs no labeled data.
- **OWL-ViT v2** — alternative open-vocab detector.
- **YOLO11n fine-tune** — fallback if zero-shot is too noisy. Need ~100–300 hand-labeled frames; tools like Roboflow or CVAT speed labeling. Check Roboflow Universe for existing climbing-hold datasets first.
- **MoonBoard / KilterBoard datasets** — standardized-board datasets exist but are specific to those boards; useful as reference, not directly applicable.

### Route matching (Stage 2)
- **DINOv2** or **CLIP** image embeddings of the wall crop → cosine similarity to cluster videos.
- Geometric: detected hold centroids → relative-position descriptor (rotation/scale-invariant hash) → match across clips.
- **OpenCV homography** to align wall views across slightly different camera angles before comparing.

### Optional: action / move recognition
- **VideoMAE v2** or **Video Swin** for action classification if we add a "move types" panel.
- Cheaper alternative: hand-crafted features from pose keypoints (vertical velocity bursts → dyno; heel-above-hip → heel hook). Probably enough for a demo.

### Optional: VLM-as-judge
- **Qwen2.5-VL** (open) or **Gemini 2.5 Flash** (hosted) on sampled frames to extract `{topped_out, route_visible_id, attempt_outcome}` as a sanity check or fallback when pose-based detection misfires.

## Performance Metrics (what the leaderboard shows)

- **Time-to-top.** From "ankles leave ground" frame → "wrist enters top-hold region" frame.
- **Attempts.** Count of on/off-wall transitions per session.
- **Smoothness.** Mean jerk of center-of-mass trajectory (lower = smoother). Or normalized path-length / vertical-displacement ratio (closer to 1 = more efficient).
- **Send rate.** Successful tops ÷ attempts.
- **Stretch:** rest time (frames where CoM doesn't move) and dynamic-move count.

## Pipeline Sketch

```
video → frame sampler (e.g. 10 fps)
  ├── pose pipeline:  YOLO11-Pose + ByteTrack → keypoint trajectories
  │     → on/off-wall detection → attempt boundaries
  │     → metrics: time, smoothness, attempts
  └── wall pipeline (Stage 2): first-frame still → Grounding DINO + SAM
        → hold positions → DINOv2 embedding + layout hash
        → route cluster ID
→ join on (climber_id, route_cluster_id) → leaderboard table
→ UI: Streamlit / simple FastAPI + static page
```

## Open Questions

- **Camera consistency.** Dataset spans unknown camera setups. Need to audit and pick the curated subset on Day 0. If most videos are handheld and move during the climb, registration will be painful — may force us back to hand-grouped routes.
- **"Top" detection.** Defining when the climb is done depends on knowing the top hold's location. Easy if the wall is fixed-camera, harder if not. Pragmatic shortcut: define top as "highest wrist position sustained for N frames."
- **Hold occlusion.** When the climber's body covers holds, layout descriptors degrade. Mitigation: use the first 1–2 seconds of video (before climber is on the wall) for the layout snapshot.
- **Dataset audit.** How many videos do we actually have, what's the resolution, what gyms, what duration? Need this before Day 1 to size the curated subset.
- **Leaderboard fairness.** Comparing climbers of different heights on the same route is noisy. Acceptable for a hackathon, but worth a caveat slide.

## Stage Plan (rough)

- **Day 0:** Dataset audit. Pick curated subset (~10–20 videos, 3–5 routes). Hand-tag climber + route for the subset.
- **Day 1:** Pose pipeline working end-to-end on one video. Trajectory overlay rendered.
- **Day 2:** Metrics computed. Leaderboard UI scaffolded with hand-grouped routes. **Demo-ready fallback exists by EOD.**
- **Day 3:** Hold detection (zero-shot first). Layout embeddings + clustering.
- **Day 4:** Route auto-matching wired into leaderboard. Polish demo path. Slides.

## Out of Scope (YAGNI)

- Mobile app / phone capture UX.
- User accounts, auth, social feed.
- Real-time inference.
- Cross-gym generalization.
- Climber re-identification from pixels.
- Fine-grained move taxonomy beyond what pose-derived heuristics give us.
- V-grade prediction from video.
