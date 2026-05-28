"""Shared pytest fixtures. Synthetic-keypoint fixtures only — no real models."""

from __future__ import annotations

import numpy as np
import pytest


def _synthetic_climb(
    n_frames: int, frame_h: int = 720, reach_top: bool = True
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build a synthetic ``(xy, conf, com_xy)`` triple for a single climber.

    Ankles start at ``y = 0.95 * H`` (on the ground) and travel up to
    ``y = 0.10 * H`` (top region) over the first 80% of frames; wrists follow
    at roughly the same trajectory shifted up by 0.05.
    """
    xy = np.zeros((n_frames, 17, 2), dtype=np.float32)
    conf = np.full((n_frames, 17), 0.9, dtype=np.float32)

    ankle_top = 0.10 * frame_h if reach_top else 0.40 * frame_h
    wrist_top = 0.05 * frame_h if reach_top else 0.35 * frame_h
    climb_frames = int(0.8 * n_frames) or 1

    for f in range(n_frames):
        progress = min(1.0, f / climb_frames)
        ankle_y = 0.95 * frame_h + (ankle_top - 0.95 * frame_h) * progress
        wrist_y = 0.90 * frame_h + (wrist_top - 0.90 * frame_h) * progress
        body_y = (ankle_y + wrist_y) / 2

        # ankles (15, 16)
        xy[f, 15] = (frame_h * 0.5 - 30, ankle_y)
        xy[f, 16] = (frame_h * 0.5 + 30, ankle_y)
        # wrists (9, 10)
        xy[f, 9] = (frame_h * 0.5 - 50, wrist_y)
        xy[f, 10] = (frame_h * 0.5 + 50, wrist_y)
        # shoulders + hips (5, 6, 11, 12) for CoM
        xy[f, 5] = (frame_h * 0.5 - 40, body_y - 60)
        xy[f, 6] = (frame_h * 0.5 + 40, body_y - 60)
        xy[f, 11] = (frame_h * 0.5 - 30, body_y + 40)
        xy[f, 12] = (frame_h * 0.5 + 30, body_y + 40)
        # head (0)
        xy[f, 0] = (frame_h * 0.5, body_y - 120)
        # knees, elbows — interpolate
        xy[f, 7] = (frame_h * 0.5 - 50, body_y - 20)
        xy[f, 8] = (frame_h * 0.5 + 50, body_y - 20)
        xy[f, 13] = (frame_h * 0.5 - 30, body_y + 80)
        xy[f, 14] = (frame_h * 0.5 + 30, body_y + 80)
    com_xy = np.column_stack(
        [np.full(n_frames, frame_h * 0.5), (xy[:, 5, 1] + xy[:, 11, 1]) / 2]
    ).astype(np.float32)
    return xy, conf, com_xy


@pytest.fixture
def successful_climb():
    """A clean send: ankles leave ground, climber reaches top, holds it."""
    return _synthetic_climb(n_frames=300, reach_top=True)


@pytest.fixture
def failed_climb():
    """A partial: climber gets halfway then stops."""
    return _synthetic_climb(n_frames=300, reach_top=False)


@pytest.fixture
def frame_h() -> int:
    return 720
