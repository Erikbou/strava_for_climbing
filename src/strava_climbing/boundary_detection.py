"""Attempt boundary detection from a single climber's pose trajectory.

Single entry point: ``find_attempts(track, frame_height) -> list[AttemptBounds]``.
The four detectors (start, top, rest, split) are internal — callers should not
need to compose them.

Image-coordinate convention used throughout: ``y=0`` is the top of the frame,
``y=H`` is the bottom. "Above" the wall means ``y < 0.8 * H`` (climber's
ankles in the upper 80% of the frame), "at the top" means ``y < 0.1 * H``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import thresholds as T

# COCO-17 indices we care about
LEFT_WRIST, RIGHT_WRIST = 9, 10
LEFT_ANKLE, RIGHT_ANKLE = 15, 16


@dataclass(slots=True, frozen=True)
class AttemptBounds:
    start_frame: int
    end_frame: int
    top_frame: int | None  # None when the climber never tops out
    send: bool


def find_attempts(
    com_xy: np.ndarray,
    kpts_xy: np.ndarray,
    kpts_conf: np.ndarray,
    frame_height: int,
) -> list[AttemptBounds]:
    """Decompose a track into one or more attempts.

    Parameters mirror :class:`pose.PoseTrack` arrays:
    - ``com_xy``  shape ``(T, 2)`` — center of mass, NaN where absent
    - ``kpts_xy`` shape ``(T, 17, 2)``
    - ``kpts_conf`` shape ``(T, 17)``
    - ``frame_height`` — video pixel height for image-space thresholds
    """
    on_wall = _on_wall_mask(kpts_xy, kpts_conf, frame_height)
    rests = _rest_mask(com_xy, frame_height)
    segments = _segments_from_mask(on_wall & ~rests)

    # If a long rest is *inside* a single on-wall segment, split it.
    split_segments: list[tuple[int, int]] = []
    for start, end in segments:
        split_segments.extend(_split_on_rest(start, end, rests))

    attempts: list[AttemptBounds] = []
    for start, end in split_segments:
        if end - start < T.START_CONSECUTIVE_FRAMES:
            continue
        top = _detect_top_frame(kpts_xy, kpts_conf, frame_height, start, end)
        send = _classify_send(top, end, rests)
        attempts.append(
            AttemptBounds(start_frame=start, end_frame=end, top_frame=top, send=send)
        )
    return attempts


# --- Internal detectors -------------------------------------------------------


def _on_wall_mask(
    xy: np.ndarray, conf: np.ndarray, frame_height: int, min_conf: float = 0.2
) -> np.ndarray:
    """Both ankles in the upper ``(1 - START_ANKLE_ABOVE_FRACTION)`` portion of the frame."""
    if xy.shape[0] == 0:
        return np.zeros(0, dtype=bool)
    threshold_y = T.START_ANKLE_ABOVE_FRACTION * frame_height
    l_ok = (conf[:, LEFT_ANKLE] >= min_conf) & (xy[:, LEFT_ANKLE, 1] < threshold_y)
    r_ok = (conf[:, RIGHT_ANKLE] >= min_conf) & (xy[:, RIGHT_ANKLE, 1] < threshold_y)
    raw = l_ok & r_ok
    # Require N consecutive frames so a single jump doesn't trigger.
    return _min_consecutive(raw, T.START_CONSECUTIVE_FRAMES)


def _rest_mask(com_xy: np.ndarray, frame_height: int) -> np.ndarray:
    """CoM low in frame AND stationary for ``REST_DURATION_FRAMES``."""
    if com_xy.shape[0] == 0:
        return np.zeros(0, dtype=bool)
    low = np.isfinite(com_xy[:, 1]) & (com_xy[:, 1] > T.REST_COM_BELOW_FRACTION * frame_height)
    stationary = np.zeros_like(low)
    win = T.REST_DURATION_FRAMES
    if com_xy.shape[0] < win:
        return stationary
    for i in range(win, com_xy.shape[0]):
        chunk = com_xy[i - win : i]
        if not np.isfinite(chunk).all():
            continue
        if (chunk.max(axis=0) - chunk.min(axis=0) < T.REST_MOVEMENT_PX).all():
            stationary[i] = True
    return low & stationary


def _segments_from_mask(mask: np.ndarray) -> list[tuple[int, int]]:
    """Convert a bool mask into (start, end_exclusive) runs."""
    out: list[tuple[int, int]] = []
    if mask.size == 0:
        return out
    edges = np.diff(mask.astype(np.int8), prepend=0, append=0)
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]
    return list(zip(starts.tolist(), ends.tolist(), strict=True))


def _split_on_rest(
    start: int, end: int, rests: np.ndarray
) -> list[tuple[int, int]]:
    """Split a segment if a rest run of ≥``REST_SPLIT_FRAMES`` occurs inside it."""
    inner = rests[start:end]
    inner_runs = _segments_from_mask(inner)
    long_rests = [(start + s, start + e) for s, e in inner_runs if e - s >= T.REST_SPLIT_FRAMES]
    if not long_rests:
        return [(start, end)]
    out: list[tuple[int, int]] = []
    cursor = start
    for rs, re_ in long_rests:
        if rs - cursor >= T.START_CONSECUTIVE_FRAMES:
            out.append((cursor, rs))
        cursor = re_
    if end - cursor >= T.START_CONSECUTIVE_FRAMES:
        out.append((cursor, end))
    return out


def _detect_top_frame(
    xy: np.ndarray,
    conf: np.ndarray,
    frame_height: int,
    start: int,
    end: int,
    min_conf: float = 0.2,
) -> int | None:
    """Earliest frame within [start, end) where the highest wrist sits in the top region
    for ``TOP_CONSECUTIVE_FRAMES`` consecutive frames.
    """
    if end - start <= T.TOP_CONSECUTIVE_FRAMES:
        return None
    threshold_y = T.TOP_WRIST_ABOVE_FRACTION * frame_height
    l_y = np.where(conf[start:end, LEFT_WRIST] >= min_conf, xy[start:end, LEFT_WRIST, 1], np.inf)
    r_y = np.where(conf[start:end, RIGHT_WRIST] >= min_conf, xy[start:end, RIGHT_WRIST, 1], np.inf)
    top_y = np.minimum(l_y, r_y)
    above = top_y < threshold_y
    run = _min_consecutive(above, T.TOP_CONSECUTIVE_FRAMES)
    idx = np.argmax(run)  # first True
    return int(start + idx) if run.any() else None


def _classify_send(top_frame: int | None, end: int, rests: np.ndarray) -> bool:
    """Send requires: top reached + held + no rest in last ``SEND_NO_REST_WINDOW_FRAMES``."""
    if top_frame is None:
        return False
    if end - top_frame < T.TOP_HOLD_FRAMES:
        return False
    window_start = max(0, top_frame - T.SEND_NO_REST_WINDOW_FRAMES)
    return not bool(rests[window_start:top_frame].any())


def _min_consecutive(mask: np.ndarray, n: int) -> np.ndarray:
    """Return a mask that is True only where at least ``n`` consecutive Trues end here.

    Implementation: rolling sum + threshold; output True at the first index where
    the trailing window has ``n`` Trues, then for all subsequent True values in
    the same run.
    """
    if mask.size == 0 or n <= 1:
        return mask.copy()
    rolled = np.zeros_like(mask, dtype=np.int32)
    rolled[0] = int(mask[0])
    for i in range(1, mask.size):
        rolled[i] = rolled[i - 1] + 1 if mask[i] else 0
    out = np.zeros_like(mask, dtype=bool)
    for i in range(mask.size):
        if rolled[i] >= n:
            # backfill the starting region of this consecutive run
            out[i - n + 1 : i + 1] = True
    return out


__all__ = ["AttemptBounds", "find_attempts"]
