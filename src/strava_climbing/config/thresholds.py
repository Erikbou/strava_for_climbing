"""Pinned-definition thresholds. See plan §"Pinned Definitions".

These ship as module-level constants so they're greppable and diff-reviewable.
Hash of this file's bytes is what populates ``attempt.config_hash`` so a
parameter change re-emits attempts on the next ``process`` run.
"""

from __future__ import annotations

import os

# --- Ingest ---------------------------------------------------------------------------
TARGET_FPS = 30
TARGET_MAX_LONG_EDGE = 1280  # 720p downsample at ingest (Addendum §E)
MIN_VIDEO_DURATION_S = 5.0
MAX_VIDEO_DURATION_S = 5 * 60.0  # auto-trim past this

# --- Pose + tracking -----------------------------------------------------------------
# yolo11n-pose is ~10x faster than 11l on CPU; the accuracy hit doesn't matter
# for our metrics (CoM trajectory + ankle/wrist position). Override with
# STRAVA_CLIMBING_POSE_MODEL=yolo11l-pose.pt if you have a GPU.
POSE_MODEL = os.environ.get("STRAVA_CLIMBING_POSE_MODEL", "yolo11n-pose.pt")
POSE_CONF = 0.35
POSE_IOU = 0.5
POSE_IMGSZ = int(os.environ.get("STRAVA_CLIMBING_POSE_IMGSZ", "480"))

# --- Attempt boundary detection ------------------------------------------------------
# Portrait-clip assumption: climber occupies most of frame; brief ankle dropouts
# (occlusion, low conf) should NOT split a single climb into many sub-attempts.
START_ANKLE_ABOVE_FRACTION = 0.95  # ankle must be in the upper 95% of frame height
START_CONSECUTIVE_FRAMES = 5
ON_WALL_GAP_CLOSE_FRAMES = 30      # bridge ≤1 s gaps in the on-wall mask
MIN_ATTEMPT_FRAMES = 90            # filter sub-3 s ghost attempts

TOP_WRIST_ABOVE_FRACTION = 0.10  # y below which wrist counts as "at top" (low y = high in frame)
TOP_CONSECUTIVE_FRAMES = 10
TOP_HOLD_FRAMES = 60  # ~2 s @ 30fps — must hold the top to count as a send

REST_COM_BELOW_FRACTION = 0.70  # CoM y must be below this (low in frame) to start a rest
REST_MOVEMENT_PX = 5.0
REST_DURATION_FRAMES = 90  # 3 s @ 30fps

REST_SPLIT_FRAMES = 150  # ≥5 s rest splits a video into two attempts

# --- Send classification --------------------------------------------------------------
SEND_NO_REST_WINDOW_FRAMES = 150  # no rest event in last 5 s before top

# --- Smoothness ----------------------------------------------------------------------
SMOOTHNESS_FROZEN_BASELINE = True  # Addendum §C recommends frozen baseline
SMOOTHNESS_MIN_ATTEMPTS_FOR_PERCENTILE = 2

# --- Multi-person disambiguation -----------------------------------------------------
# Track with the largest cumulative vertical climb wins.

# --- Anthropometric weights (Winter 1990, % body mass) ------------------------------
# Used to estimate center-of-mass from COCO-17 keypoints.
ANTHROPOMETRIC_WEIGHTS = {
    # name: (keypoint indices to average, mass fraction)
    "head": ([0], 0.0810),
    "torso": ([5, 6, 11, 12], 0.4970),
    "upper_arm_l": ([5, 7], 0.0280),
    "upper_arm_r": ([6, 8], 0.0280),
    "forearm_l": ([7, 9], 0.0220),
    "forearm_r": ([8, 10], 0.0220),
    "thigh_l": ([11, 13], 0.1000),
    "thigh_r": ([12, 14], 0.1000),
    "shank_l": ([13, 15], 0.0465),
    "shank_r": ([14, 16], 0.0465),
}
