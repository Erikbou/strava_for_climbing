"""Kinematic helpers operating on landmark arrays.

All functions are vectorized over time: pass per-frame point arrays of shape
(N, 3) (or (N, 2)) and get back per-frame results of shape (N,).
"""

from __future__ import annotations

import numpy as np


def angle_between(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Interior angle (degrees) at vertex `b` of the path a-b-c.

    Accepts single points of shape (D,) or stacks of shape (N, D); returns a
    scalar or an (N,) array of degrees in [0, 180].
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    c = np.asarray(c, dtype=np.float64)
    v1 = a - b
    v2 = c - b
    dot = np.sum(v1 * v2, axis=-1)
    n1 = np.linalg.norm(v1, axis=-1)
    n2 = np.linalg.norm(v2, axis=-1)
    denom = np.clip(n1 * n2, 1e-9, None)
    cos = np.clip(dot / denom, -1.0, 1.0)
    return np.degrees(np.arccos(cos))


def trunk_center(points: np.ndarray, idx) -> np.ndarray:
    """Center-of-mass proxy: mean of the four trunk landmarks per frame.

    `points` is (N, 33, D); `idx` is the LANDMARK_INDEX mapping. Using the
    shoulder/hip quad is far more stable than any single joint.
    """
    keys = ["left_shoulder", "right_shoulder", "left_hip", "right_hip"]
    sel = points[:, [idx[k] for k in keys], :]
    return sel.mean(axis=1)


def moving_average(x: np.ndarray, window: int = 5) -> np.ndarray:
    """Smooth along the time axis (axis 0) with edge-reflected padding.

    Reduces landmark jitter. `window` is clamped to odd and to the series
    length. Works on arrays of any trailing shape.
    """
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[0]
    if n < 3 or window < 3:
        return x
    window = min(window, n if n % 2 else n - 1)
    if window % 2 == 0:
        window -= 1
    if window < 3:
        return x
    pad = window // 2
    kernel = np.ones(window) / window
    padded = np.pad(x, [(pad, pad)] + [(0, 0)] * (x.ndim - 1), mode="reflect")
    out = np.empty_like(x)
    flat_in = padded.reshape(padded.shape[0], -1)
    flat_out = out.reshape(out.shape[0], -1)
    for c in range(flat_in.shape[1]):
        flat_out[:, c] = np.convolve(flat_in[:, c], kernel, mode="valid")
    return out


def speed(points: np.ndarray) -> np.ndarray:
    """Total per-frame motion: summed landmark displacement between frames.

    Returns (N,) where element 0 is 0. Peaks correspond to dynamic moves;
    near-zero stretches are static holds.
    """
    diff = np.diff(points, axis=0)
    step = np.linalg.norm(diff, axis=-1).sum(axis=1)
    return np.concatenate([[0.0], step])
