"""Auto-highlight clip extractor per Leonard's product brief, Feature 3.

Picks the most "interesting" seconds of the send and trims them out with
ffmpeg. v1 heuristic: peak |CoM vertical velocity| → centre a window there.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .boundary_detection import AttemptBounds

_DEFAULT_WINDOW_SECONDS = 4.0


def pick_highlight_window(
    bounds: AttemptBounds,
    com_xy: np.ndarray,
    fps: float,
    *,
    window_seconds: float = _DEFAULT_WINDOW_SECONDS,
) -> tuple[float, float]:
    """Return (start_seconds, duration_seconds) for the highlight clip.

    Strategy: take the frame inside the attempt with the largest |vertical
    velocity| of CoM as the centre of a fixed-length window, clipped to the
    attempt bounds.
    """
    fps = max(fps, 1.0)
    start, end = bounds.start_frame, bounds.end_frame
    com_slice = com_xy[start:end]
    if com_slice.shape[0] < 2:
        return (start / fps, window_seconds)

    y = com_slice[:, 1]
    if not np.isfinite(y).any():
        peak_frame = (end - start) // 2
    else:
        idx = np.arange(y.size)
        good = np.isfinite(y)
        y_interp = np.interp(idx, idx[good], y[good])
        v = np.abs(np.diff(y_interp))  # px/frame; scale doesn't matter for argmax
        peak_frame = int(v.argmax())

    centre_seconds = (start + peak_frame) / fps
    attempt_start_s = start / fps
    attempt_end_s = end / fps
    half = window_seconds / 2.0

    clip_start = max(attempt_start_s, centre_seconds - half)
    clip_end = min(attempt_end_s, clip_start + window_seconds)
    if clip_end - clip_start < window_seconds:
        clip_start = max(attempt_start_s, clip_end - window_seconds)
    return (clip_start, max(0.5, clip_end - clip_start))


def render_highlight(
    video_path: Path,
    out_path: Path,
    *,
    start_seconds: float,
    duration_seconds: float,
) -> None:
    """ffmpeg trim into a self-contained MP4 with +faststart for streaming."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start_seconds:.3f}",
        "-i",
        str(video_path),
        "-t",
        f"{duration_seconds:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


__all__ = ["pick_highlight_window", "render_highlight"]
