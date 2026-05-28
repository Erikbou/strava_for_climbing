"""MovementSequence -> kinematic metrics + chart PNG.

Joint angles and limb motion come from the camera-invariant *world* landmarks.
Climb progress (vertical travel up the wall) comes from *pixel* coordinates,
since world landmarks are hip-rooted and carry no global translation.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .schema import MovementSequence, LANDMARK_INDEX
from . import geometry as geo

_SMOOTH = 7


def compute_metrics(seq: MovementSequence) -> dict:
    """Per-frame kinematic series derived from the movement sequence."""
    i = LANDMARK_INDEX
    w = seq.world

    def angle(a, b, c):
        return geo.moving_average(
            geo.angle_between(w[:, i[a]], w[:, i[b]], w[:, i[c]]), _SMOOTH
        )

    # Climb progress: hip-center height in pixels, normalized, up = positive.
    hip_y = seq.pixels[:, [i["left_hip"], i["right_hip"]], 1].mean(axis=1)
    progress = geo.moving_average((seq.height - hip_y) / seq.height, _SMOOTH)

    motion = geo.moving_average(geo.speed(w), _SMOOTH)

    return {
        "t": seq.times,
        "elbow_left": angle("left_shoulder", "left_elbow", "left_wrist"),
        "elbow_right": angle("right_shoulder", "right_elbow", "right_wrist"),
        "knee_left": angle("left_hip", "left_knee", "left_ankle"),
        "knee_right": angle("right_hip", "right_knee", "right_ankle"),
        "hip_left": angle("left_shoulder", "left_hip", "left_knee"),
        "hip_right": angle("right_shoulder", "right_hip", "right_knee"),
        "progress": progress,
        "motion": motion,
    }


def plot_analytics(seq: MovementSequence, out_path: str) -> str:
    """Render a 4-panel summary chart to `out_path`."""
    m = compute_metrics(seq)
    t = m["t"]

    fig, axes = plt.subplots(4, 1, figsize=(11, 12), sharex=True)
    fig.suptitle("Climb movement analytics", fontsize=15, fontweight="bold")

    ax = axes[0]
    ax.plot(t, m["elbow_left"], label="left", color="#3ca0ff")
    ax.plot(t, m["elbow_right"], label="right", color="#ff7a3c")
    ax.set_ylabel("elbow angle (deg)")
    ax.legend(loc="upper right"); ax.grid(alpha=0.3)

    ax = axes[1]
    ax.plot(t, m["knee_left"], label="left", color="#3ca0ff")
    ax.plot(t, m["knee_right"], label="right", color="#ff7a3c")
    ax.set_ylabel("knee angle (deg)")
    ax.legend(loc="upper right"); ax.grid(alpha=0.3)

    ax = axes[2]
    ax.plot(t, m["progress"], color="#43c463")
    ax.fill_between(t, m["progress"], alpha=0.2, color="#43c463")
    ax.set_ylabel("climb progress\n(hip height, norm.)")
    ax.grid(alpha=0.3)

    ax = axes[3]
    ax.plot(t, m["motion"], color="#b06bff")
    ax.fill_between(t, m["motion"], alpha=0.2, color="#b06bff")
    ax.set_ylabel("movement speed\n(m/frame, body-rel.)")
    ax.set_xlabel("time (s)")
    ax.grid(alpha=0.3)
    _annotate_peaks(ax, t, m["motion"])

    fig.tight_layout(rect=(0, 0, 1, 0.98))
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
    return out_path


def _annotate_peaks(ax, t: np.ndarray, motion: np.ndarray) -> None:
    """Mark the most dynamic moments (local maxima above a threshold)."""
    if motion.size < 3:
        return
    thr = motion.mean() + motion.std()
    for k in range(1, len(motion) - 1):
        if motion[k] > thr and motion[k] >= motion[k - 1] and motion[k] > motion[k + 1]:
            ax.axvline(t[k], color="#b06bff", alpha=0.25, linestyle="--")
