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

# Burst threshold expressed as a *fraction of frame height per second* so the
# detector scales with video resolution and doesn't need re-tuning per clip.
# Portrait-clip baseline: 0.04 (~29 px/s on a 720-tall clip) flags the moves
# climbers actually feel as dynamic without picking up sway/breathing jitter.
_DYNAMIC_VEL_FRAC_HEIGHT_PER_S = 0.04
_DYNAMIC_MIN_RUN_FRAMES = 3
_DYNAMIC_GAP_FRAMES = 6

# "Idle" = vertical speed below 3% of frame height per second.
_IDLE_VEL_FRAC_HEIGHT_PER_S = 0.03


@dataclass(slots=True, frozen=True)
class BodyStats:
    dynamic_moves: int
    longest_reach_px: float
    hang_time_seconds: float
    idle_seconds: float


def compute(
    bounds: AttemptBounds,
    xy: np.ndarray,
    com_xy: np.ndarray,
    fps: float,
    frame_height: int,
) -> BodyStats:
    """Compute body-derived stats for a single attempt window.

    ``xy`` is the full ``(T, 17, 2)`` keypoint array; ``com_xy`` is ``(T, 2)``.
    Frames outside ``[bounds.start_frame, bounds.end_frame]`` are ignored.
    Velocity thresholds scale with ``frame_height`` so portrait clips of
    different resolutions all get the same physical sensitivity.
    """
    start, end = bounds.start_frame, bounds.end_frame
    com_slice = com_xy[start:end]
    xy_slice = xy[start:end]
    fps = max(fps, 1.0)
    dt = 1.0 / fps

    burst_threshold = _DYNAMIC_VEL_FRAC_HEIGHT_PER_S * frame_height
    idle_threshold = _IDLE_VEL_FRAC_HEIGHT_PER_S * frame_height

    vy = _vertical_speed(com_slice, dt)  # px/sec
    speed = np.abs(vy)

    return BodyStats(
        dynamic_moves=_count_dynamic_moves(vy, burst_threshold),
        longest_reach_px=_longest_reach(xy_slice),
        hang_time_seconds=_longest_idle_run(speed, idle_threshold) * dt,
        idle_seconds=float((speed < idle_threshold).sum()) * dt,
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


def _count_dynamic_moves(vy: np.ndarray, threshold_px_per_s: float) -> int:
    """A dynamic move = a contiguous run of frames where the climber is moving
    UP fast (image y decreasing, so vy < -threshold), separated from the next
    burst by at least `_DYNAMIC_GAP_FRAMES` quiet frames.
    """
    if vy.size == 0:
        return 0
    burst = vy < -threshold_px_per_s
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


def _longest_idle_run(speed: np.ndarray, threshold_px_per_s: float) -> int:
    """Longest contiguous run of frames where speed < threshold."""
    if speed.size == 0:
        return 0
    idle = speed < threshold_px_per_s
    best = run = 0
    for v in idle:
        if v:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


__all__ = ["BodyStats", "compute"]
