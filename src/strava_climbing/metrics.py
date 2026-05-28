"""Per-attempt metrics + route-level percentile computation.

Pure functions over numpy arrays. No DB or file I/O lives here so tests can
exercise the math with synthetic fixtures.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .boundary_detection import AttemptBounds
from .config import thresholds as T


@dataclass(slots=True, frozen=True)
class AttemptMetrics:
    time_seconds: float
    smoothness_raw: float
    attempts_count: int
    send: bool


def compute_metrics(
    bounds: AttemptBounds, com_xy: np.ndarray, fps: float, *, attempts_count: int = 1
) -> AttemptMetrics:
    """Compute time-to-top + smoothness for a single attempt.

    Time-to-top is measured from ``start_frame`` to ``top_frame`` when the
    climber tops out, otherwise to ``end_frame`` (records "how long they were
    on the wall before falling").
    """
    end_for_time = bounds.top_frame if bounds.top_frame is not None else bounds.end_frame
    n_frames = max(1, end_for_time - bounds.start_frame)
    time_seconds = n_frames / max(fps, 1.0)
    smoothness = _mean_jerk(com_xy[bounds.start_frame : end_for_time + 1], fps)
    return AttemptMetrics(
        time_seconds=float(time_seconds),
        smoothness_raw=float(smoothness) if math.isfinite(smoothness) else float("nan"),
        attempts_count=attempts_count,
        send=bounds.send,
    )


def _mean_jerk(com_xy: np.ndarray, fps: float) -> float:
    """Mean magnitude of jerk (3rd time derivative) of CoM.

    NaN frames are linearly interpolated before differentiation; if there are
    too few finite samples the metric is NaN.
    """
    if com_xy.shape[0] < 8:
        return float("nan")
    series = _interp_nans(com_xy)
    if not np.isfinite(series).all():
        return float("nan")
    dt = 1.0 / max(fps, 1.0)
    # Central differences keep ordering; np.diff gives forward differences.
    velocity = np.diff(series, axis=0) / dt
    accel = np.diff(velocity, axis=0) / dt
    jerk = np.diff(accel, axis=0) / dt
    mag = np.linalg.norm(jerk, axis=1)
    return float(mag.mean())


def _interp_nans(arr: np.ndarray) -> np.ndarray:
    """Linearly interpolate NaN values column-wise."""
    out = arr.copy()
    for c in range(arr.shape[1]):
        col = out[:, c]
        bad = ~np.isfinite(col)
        if not bad.any():
            continue
        if bad.all():
            return out  # caller will see NaNs and treat as missing
        good = np.where(~bad)[0]
        out[bad, c] = np.interp(np.where(bad)[0], good, col[good])
    return out


def compute_route_percentiles(
    raws: list[float], *, frozen_baseline: list[float] | None = None
) -> list[float | None]:
    """Map raw smoothness values to per-route percentiles in [0, 100].

    Lower raw jerk = smoother = higher percentile.

    If ``frozen_baseline`` is provided, percentiles are computed against that
    distribution (the recommended Strava-like UX from Addendum §C) so adding
    new attempts doesn't silently shift old scores. New attempts may exceed
    the [0, 100] range when ranked against the baseline; we clip on display.
    """
    if not raws:
        return []
    finite_raws = [r for r in raws if r is not None and math.isfinite(r)]
    if len(finite_raws) < T.SMOOTHNESS_MIN_ATTEMPTS_FOR_PERCENTILE:
        return [None] * len(raws)

    baseline = frozen_baseline if frozen_baseline else finite_raws
    baseline_sorted = np.sort(np.asarray(baseline, dtype=np.float64))

    out: list[float | None] = []
    for r in raws:
        if r is None or not math.isfinite(r):
            out.append(None)
            continue
        # Lower jerk → higher percentile. Use right-side rank then invert.
        rank = np.searchsorted(baseline_sorted, r, side="right")
        pct = 100.0 * (1.0 - rank / len(baseline_sorted))
        out.append(float(max(0.0, min(100.0, pct))))
    return out


def config_hash(*sources: Path) -> str:
    """SHA-256 of one or more config files. Use this for ``attempt.config_hash``."""
    h = hashlib.sha256()
    for src in sources:
        h.update(src.read_bytes())
    return h.hexdigest()


def current_config_hash() -> str:
    """Hash of the pinned-definitions module — bumps whenever a threshold changes."""
    return config_hash(Path(T.__file__))


__all__ = [
    "AttemptMetrics",
    "compute_metrics",
    "compute_route_percentiles",
    "config_hash",
    "current_config_hash",
]
