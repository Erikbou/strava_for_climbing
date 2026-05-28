"""Heuristic body-derived stats per Leonard's product brief.

Pure functions over the existing pose track + attempt window. No DB or file I/O.
The stats land on the post page as "things a climber actually cares about" —
explicitly NOT every value the pose model can emit.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .boundary_detection import AttemptBounds

# COCO-17 indices
_LEFT_WRIST = 9
_RIGHT_WRIST = 10
_LEFT_HIP = 11
_RIGHT_HIP = 12

# Vertical velocity (px/sec) threshold above which a frame counts as a "burst".
# A dynamic move is a contiguous run of burst frames separated by quiet frames.
_DYNAMIC_VEL_PX_PER_S = 220.0
_DYNAMIC_MIN_RUN_FRAMES = 2
_DYNAMIC_GAP_FRAMES = 6

# "Idle" = velocity below this (px/sec). Used for both hang-time and total idle.
_IDLE_VEL_PX_PER_S = 25.0


@dataclass(slots=True, frozen=True)
class BodyStats:
    dynamic_moves: int
    longest_reach_px: float
    hang_time_seconds: float
    idle_seconds: float


def compute(bounds: AttemptBounds, xy: np.ndarray, com_xy: np.ndarray, fps: float) -> BodyStats:
    """Compute body-derived stats for a single attempt window.

    ``xy`` is the full ``(T, 17, 2)`` keypoint array; ``com_xy`` is ``(T, 2)``.
    Frames outside ``[bounds.start_frame, bounds.end_frame]`` are ignored.
    """
    start, end = bounds.start_frame, bounds.end_frame
    com_slice = com_xy[start:end]
    xy_slice = xy[start:end]
    fps = max(fps, 1.0)
    dt = 1.0 / fps

    vy = _vertical_speed(com_slice, dt)  # px/sec
    speed = np.abs(vy)

    return BodyStats(
        dynamic_moves=_count_dynamic_moves(vy),
        longest_reach_px=_longest_reach(xy_slice),
        hang_time_seconds=_longest_idle_run(speed) * dt,
        idle_seconds=float((speed < _IDLE_VEL_PX_PER_S).sum()) * dt,
    )


def _vertical_speed(com: np.ndarray, dt: float) -> np.ndarray:
    """Signed vertical speed (px/sec); upward = negative in image coords."""
    if com.shape[0] < 2:
        return np.zeros(0, dtype=np.float64)
    y = com[:, 1]
    finite = np.isfinite(y)
    if not finite.any():
        return np.zeros(com.shape[0] - 1, dtype=np.float64)
    # Linearly interpolate NaNs so diff doesn't propagate them.
    if not finite.all():
        idx = np.arange(len(y))
        y = np.interp(idx, idx[finite], y[finite])
    return np.diff(y) / dt


def _count_dynamic_moves(vy: np.ndarray) -> int:
    """A dynamic move = a contiguous run of frames where the climber is moving
    UP fast (image y decreasing, so vy < -threshold), separated from the next
    burst by at least `_DYNAMIC_GAP_FRAMES` quiet frames.
    """
    if vy.size == 0:
        return 0
    burst = vy < -_DYNAMIC_VEL_PX_PER_S
    moves = 0
    run = 0
    gap = 0
    in_move = False
    for b in burst:
        if b:
            run += 1
            gap = 0
            if run >= _DYNAMIC_MIN_RUN_FRAMES and not in_move:
                moves += 1
                in_move = True
        else:
            gap += 1
            run = 0
            if gap >= _DYNAMIC_GAP_FRAMES:
                in_move = False
    return moves


def _longest_reach(xy_slice: np.ndarray) -> float:
    """Per-frame max wrist-to-hip vertical extension; return the global max.

    Approximates "longest reach": how far above the hip the higher wrist got.
    Image y is inverted, so reach = hip_y - wrist_y when wrist is above hip.
    """
    if xy_slice.size == 0:
        return 0.0
    wrist_y = np.nanmin(
        np.stack([xy_slice[:, _LEFT_WRIST, 1], xy_slice[:, _RIGHT_WRIST, 1]], axis=0),
        axis=0,
    )
    hip_y = np.nanmean(
        np.stack([xy_slice[:, _LEFT_HIP, 1], xy_slice[:, _RIGHT_HIP, 1]], axis=0),
        axis=0,
    )
    reach = hip_y - wrist_y  # positive when wrist above hip
    reach = reach[np.isfinite(reach)]
    if reach.size == 0:
        return 0.0
    return float(reach.max())


def _longest_idle_run(speed: np.ndarray) -> int:
    """Longest contiguous run of frames where speed < _IDLE_VEL_PX_PER_S."""
    if speed.size == 0:
        return 0
    idle = speed < _IDLE_VEL_PX_PER_S
    best = run = 0
    for v in idle:
        if v:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


__all__ = ["BodyStats", "compute"]
