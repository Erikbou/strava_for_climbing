"""MovementSequence + work video -> skeleton-overlay MP4."""

from __future__ import annotations

import cv2
import numpy as np

from .schema import MovementSequence, POSE_CONNECTIONS, LANDMARK_INDEX, LANDMARK_NAMES
from . import geometry as geo

_VIS_THRESH = 0.4

# Landmark side coloring (BGR).
_LEFT = {i for i, n in enumerate(LANDMARK_NAMES) if n.startswith("left_")}
_RIGHT = {i for i, n in enumerate(LANDMARK_NAMES) if n.startswith("right_")}


def _joint_color(i: int) -> tuple[int, int, int]:
    if i in _LEFT:
        return (255, 180, 60)   # blue-ish
    if i in _RIGHT:
        return (60, 160, 255)   # orange-ish
    return (240, 240, 240)      # center / face


def render_overlay(
    seq: MovementSequence,
    work_video: str,
    out_path: str,
    draw_metrics: bool = True,
) -> str:
    """Draw the pose skeleton onto each frame of `work_video` -> `out_path`."""
    cap = cv2.VideoCapture(work_video)
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {work_video}")
    w, h = seq.width, seq.height
    writer = cv2.VideoWriter(
        out_path, cv2.VideoWriter_fourcc(*"mp4v"), seq.fps, (w, h)
    )

    elbow = None
    if draw_metrics:
        elbow = _avg_elbow_angle(seq)

    px = seq.pixels
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok or idx >= seq.num_frames:
            break
        _draw_skeleton(frame, px[idx])
        if draw_metrics:
            _draw_hud(frame, idx, seq.fps, float(elbow[idx]))
        writer.write(frame)
        idx += 1

    cap.release()
    writer.release()
    return out_path


def _draw_skeleton(frame: np.ndarray, pts: np.ndarray) -> None:
    for a, b in POSE_CONNECTIONS:
        if pts[a, 2] < _VIS_THRESH or pts[b, 2] < _VIS_THRESH:
            continue
        pa = (int(pts[a, 0]), int(pts[a, 1]))
        pb = (int(pts[b, 0]), int(pts[b, 1]))
        cv2.line(frame, pa, pb, (80, 220, 120), 2, cv2.LINE_AA)
    for i in range(pts.shape[0]):
        if pts[i, 2] < _VIS_THRESH:
            continue
        c = (int(pts[i, 0]), int(pts[i, 1]))
        cv2.circle(frame, c, 4, _joint_color(i), -1, cv2.LINE_AA)


def _draw_hud(frame: np.ndarray, idx: int, fps: float, elbow_deg: float) -> None:
    t = idx / fps
    lines = [f"t={t:5.2f}s  frame {idx}", f"elbow {elbow_deg:5.1f} deg"]
    y = 30
    for line in lines:
        cv2.putText(frame, line, (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(frame, line, (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (255, 255, 255), 1, cv2.LINE_AA)
        y += 32


def _avg_elbow_angle(seq: MovementSequence) -> np.ndarray:
    """Mean of left+right elbow angles per frame (from world landmarks)."""
    i = LANDMARK_INDEX
    w = seq.world
    left = geo.angle_between(w[:, i["left_shoulder"]], w[:, i["left_elbow"]], w[:, i["left_wrist"]])
    right = geo.angle_between(w[:, i["right_shoulder"]], w[:, i["right_elbow"]], w[:, i["right_wrist"]])
    return geo.moving_average(np.nanmean(np.stack([left, right], axis=1), axis=1), 5)
