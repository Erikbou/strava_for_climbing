"""Movement-section similarity search (lightweight, no-train baseline).

Turns sliding windows of a climb into camera/scale-invariant motion descriptors
(pooled joint angles + angular velocities + body-relative motion energy) and
finds similar sections by cosine similarity.

Prototype substrate: the MVP's MediaPipe 3D `output/keypoints.npz` (hip-rooted
world coords). Designed to graduate into the platform later (multi-clip index,
pgvector) behind the same `descriptors()` -> vectors interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import geometry as geo
from .schema import LANDMARK_INDEX, MovementSequence

# Joint angles that characterize a climbing move. Vertex is the middle joint.
ANGLE_DEFS: list[tuple[str, tuple[str, str, str]]] = [
    ("elbow_l", ("left_shoulder", "left_elbow", "left_wrist")),
    ("elbow_r", ("right_shoulder", "right_elbow", "right_wrist")),
    ("knee_l", ("left_hip", "left_knee", "left_ankle")),
    ("knee_r", ("right_hip", "right_knee", "right_ankle")),
    ("hip_l", ("left_shoulder", "left_hip", "left_knee")),
    ("hip_r", ("right_shoulder", "right_hip", "right_knee")),
    ("shoulder_l", ("left_elbow", "left_shoulder", "left_hip")),
    ("shoulder_r", ("right_elbow", "right_shoulder", "right_hip")),
]


@dataclass(slots=True)
class SectionIndex:
    """A searchable set of window descriptors over one or more climbs."""

    vectors: np.ndarray          # (N, D) standardized + L2-normalized
    meta: list[dict]             # per-window {clip, start_frame, end_frame, t0, t1}
    mean: np.ndarray             # (D,) column scaler
    std: np.ndarray              # (D,)

    def search(
        self, query: int, k: int = 5, *, exclude_radius: int = 1, same_clip: bool = True
    ) -> list[tuple[int, float]]:
        """Top-k windows most similar to window `query` (cosine).

        `exclude_radius` drops the query and its temporally-adjacent windows in
        the *same clip* so results aren't dominated by trivial overlap. With
        `same_clip=False`, the whole query clip is excluded (cross-clip search).
        """
        sims = self.vectors @ self.vectors[query]
        q = self.meta[query]
        for i, m in enumerate(self.meta):
            same = m["clip"] == q["clip"]
            if i == query or (same and not same_clip) or (
                same and abs(m["window_idx"] - q["window_idx"]) <= exclude_radius
            ):
                sims[i] = -np.inf
        order = np.argsort(sims)[::-1][:k]
        return [(int(i), float(sims[i])) for i in order]


def frozen_mask(world: np.ndarray) -> np.ndarray:
    """(T,) bool — True where a frame is a forward-filled duplicate of the prior.

    Extraction forward-fills frames with no detected pose by copying the last
    valid frame bit-for-bit, so an exact match to the previous frame flags a
    'no real pose here' frame. Real frames are never bitwise identical.
    """
    if world.shape[0] < 2:
        return np.zeros(world.shape[0], dtype=bool)
    moved = np.any(world[1:] != world[:-1], axis=(1, 2))
    return np.concatenate([[False], ~moved])


def angle_series(world: np.ndarray, *, smooth: int = 5) -> np.ndarray:
    """(T, 33, 3) world landmarks -> (T, A) smoothed joint angles in degrees."""
    cols = []
    for _, (a, b, c) in ANGLE_DEFS:
        ia, ib, ic = LANDMARK_INDEX[a], LANDMARK_INDEX[b], LANDMARK_INDEX[c]
        cols.append(geo.angle_between(world[:, ia], world[:, ib], world[:, ic]))
    angles = np.stack(cols, axis=1)
    return geo.moving_average(angles, smooth)


def _window_descriptor(angles: np.ndarray, ang_vel: np.ndarray, energy: np.ndarray) -> np.ndarray:
    """Pool a window's per-frame features into one fixed-length vector."""
    feats = [
        angles.mean(0), angles.std(0), angles.min(0), angles.max(0),
        np.abs(ang_vel).mean(0), np.abs(ang_vel).max(0),
        np.array([energy.mean()]),
    ]
    return np.concatenate(feats)


def descriptors(
    seq: MovementSequence, *, win_seconds: float = 1.0, stride_seconds: float = 0.5,
    clip: str = "clip", min_quality: float = 0.5,
) -> tuple[np.ndarray, list[dict]]:
    """Raw (un-standardized) window descriptors for one climb + window metadata.

    Windows that are more than ``1 - min_quality`` forward-filled (no real pose)
    are dropped so cuts / wide shots don't pollute the index.
    """
    win = max(2, round(win_seconds * seq.fps))
    stride = max(1, round(stride_seconds * seq.fps))
    angles = angle_series(seq.world)
    ang_vel = np.diff(angles, axis=0, prepend=angles[:1])
    energy = geo.speed(seq.world)  # body-relative (hip-rooted world coords)
    frozen = frozen_mask(seq.world)

    raws: list[np.ndarray] = []
    meta: list[dict] = []
    widx = 0
    for s in range(0, max(1, angles.shape[0] - win + 1), stride):
        e = s + win
        if 1.0 - frozen[s:e].mean() < min_quality:
            continue
        raws.append(_window_descriptor(angles[s:e], ang_vel[s:e], energy[s:e]))
        meta.append({
            "clip": clip, "window_idx": widx,
            "start_frame": s, "end_frame": e,
            "t0": round(s / seq.fps, 2), "t1": round(e / seq.fps, 2),
        })
        widx += 1
    return np.asarray(raws), meta


def build_index(per_clip: list[tuple[np.ndarray, list[dict]]]) -> SectionIndex:
    """Standardize per-column across all windows, L2-normalize rows -> SectionIndex."""
    raw = np.concatenate([r for r, _ in per_clip], axis=0)
    meta = [m for _, ms in per_clip for m in ms]
    mean = raw.mean(0)
    std = raw.std(0) + 1e-8
    z = (raw - mean) / std
    z /= np.linalg.norm(z, axis=1, keepdims=True) + 1e-8
    return SectionIndex(vectors=z, meta=meta, mean=mean, std=std)


def load_index(path: str, *, win_seconds: float = 1.0, stride_seconds: float = 0.5) -> SectionIndex:
    """Build a SectionIndex from a single keypoints.npz or a directory of them."""
    p = Path(path)
    files = sorted(p.glob("*.npz")) if p.is_dir() else [p]
    if not files:
        raise SystemExit(f"no .npz found at {path}")
    per_clip = [
        descriptors(MovementSequence.load_npz(str(f)), win_seconds=win_seconds,
                    stride_seconds=stride_seconds, clip=f.stem)
        for f in files
    ]
    return build_index(per_clip)


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Movement-section similarity search")
    p.add_argument("path", help="keypoints.npz file OR a directory of them")
    p.add_argument("--win", type=float, default=1.0)
    p.add_argument("--stride", type=float, default=0.5)
    p.add_argument("--k", type=int, default=3)
    args = p.parse_args()

    idx = load_index(args.path, win_seconds=args.win, stride_seconds=args.stride)
    n = len(idx.meta)
    clips = sorted({m["clip"] for m in idx.meta})
    multi = len(clips) > 1
    print(f"{len(clips)} clip(s), {n} windows ({args.win}s / {args.stride}s stride), "
          f"descriptor dim {idx.vectors.shape[1]}")

    self_ok = sum(int(np.argmax(idx.vectors @ idx.vectors[i]) == i) for i in range(n))
    print(f"self-retrieval sanity: {self_ok}/{n} windows rank themselves #1")
    print(f"mode: {'CROSS-clip' if multi else 'within-clip'} search\n")

    for q in np.linspace(0, n - 1, min(6, n), dtype=int):
        m = idx.meta[q]
        print(f"query [{m['clip']}] t={m['t0']:.1f}-{m['t1']:.1f}s")
        for rank, (j, sim) in enumerate(idx.search(q, k=args.k, same_clip=not multi), 1):
            mj = idx.meta[j]
            print(f"   #{rank}  [{mj['clip']}] t={mj['t0']:.1f}-{mj['t1']:.1f}s   cos={sim:.3f}")
        print()


if __name__ == "__main__":
    main()
