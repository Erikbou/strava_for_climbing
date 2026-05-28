"""Pose extraction + multi-person tracking + climber-track selection.

Wraps Ultralytics YOLO11l-pose with the BoT-SORT tracker. Per-frame keypoints
are accumulated in dense numpy arrays and persisted to ``.npz`` for downstream
modules (boundary detection, metrics, overlay) so we never re-run inference.

Climber-track selection: among all observed tracks, pick the one with the
largest cumulative vertical climb (max_y - min_y of estimated CoM), breaking
ties by track duration. See Pinned Definitions in the plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import paths as P
from .config import thresholds as T

# COCO-17 keypoint count. Set as a constant so we don't depend on torch types.
N_KP = 17


@dataclass(slots=True, frozen=True)
class PoseTrack:
    """Per-track per-frame pose data. NaN where the track is absent on that frame."""

    track_id: int
    xy: np.ndarray  # (T, 17, 2)
    conf: np.ndarray  # (T, 17)
    com_xy: np.ndarray  # (T, 2) — center of mass, NaN where absent


def run_pose(video_path: Path, *, cache_path: Path | None = None) -> dict[int, PoseTrack]:
    """Run YOLO11l-pose + BoT-SORT on a normalized video.

    Returns a dict ``{track_id: PoseTrack}``. Also persists the raw arrays to
    ``cache_path`` (defaults to ``data/cache/pose/{stem}.npz``) so re-runs of
    downstream stages don't re-invoke the model.
    """
    from ultralytics import YOLO

    cache = cache_path or (P.POSE_CACHE_DIR / f"{video_path.stem}.npz")
    cache.parent.mkdir(parents=True, exist_ok=True)

    model = YOLO(T.POSE_MODEL)
    results = model.track(
        source=str(video_path),
        tracker="botsort.yaml",
        persist=True,
        conf=T.POSE_CONF,
        iou=T.POSE_IOU,
        imgsz=T.POSE_IMGSZ,
        stream=True,
        verbose=False,
    )

    # Sparse collection: track_id -> {frame_idx: (xy[17,2], conf[17])}
    sparse: dict[int, dict[int, tuple[np.ndarray, np.ndarray]]] = {}
    n_frames = 0

    for f_idx, r in enumerate(results):
        n_frames = f_idx + 1
        if r.boxes is None or r.boxes.id is None or r.keypoints is None:
            continue
        track_ids = r.boxes.id.int().cpu().numpy()
        kpts_xy = r.keypoints.xy.cpu().numpy()  # (N, 17, 2)
        kpts_conf = r.keypoints.conf
        kpts_conf = kpts_conf.cpu().numpy() if kpts_conf is not None else np.ones(kpts_xy.shape[:2])
        for i, tid in enumerate(track_ids):
            sparse.setdefault(int(tid), {})[f_idx] = (kpts_xy[i], kpts_conf[i])

    if n_frames == 0:
        raise RuntimeError(f"pose: no frames decoded from {video_path}")

    tracks = _materialize_tracks(sparse, n_frames)
    _save_cache(cache, tracks, n_frames)
    return tracks


def load_pose_cache(cache_path: Path) -> dict[int, PoseTrack]:
    """Reload a previously persisted pose result."""
    with np.load(cache_path) as z:
        track_ids = z["track_ids"]
        xy = z["xy"]  # (K, T, 17, 2)
        conf = z["conf"]  # (K, T, 17)
        com = z["com_xy"]  # (K, T, 2)
    out: dict[int, PoseTrack] = {}
    for i, tid in enumerate(track_ids):
        out[int(tid)] = PoseTrack(
            track_id=int(tid), xy=xy[i], conf=conf[i], com_xy=com[i]
        )
    return out


def pick_climber_track(tracks: dict[int, PoseTrack]) -> int | None:
    """Pick the track with the largest cumulative vertical climb of CoM.

    Tie-broken by track duration (number of frames present). Returns ``None``
    when no track has any usable frames.
    """
    if not tracks:
        return None
    best_id = None
    best = (-np.inf, 0)  # (climb, duration)
    for tid, t in tracks.items():
        com_y = t.com_xy[:, 1]
        present = ~np.isnan(com_y)
        if not present.any():
            continue
        ys = com_y[present]
        # Climb is max - min in image y. Lower y = higher in frame, so flip sign:
        climb = float(ys.max() - ys.min())
        duration = int(present.sum())
        if (climb, duration) > best:
            best = (climb, duration)
            best_id = tid
    return best_id


def estimate_com(xy: np.ndarray, conf: np.ndarray, *, min_conf: float = 0.2) -> np.ndarray:
    """Weighted CoM per frame using Winter-1990 segment masses.

    ``xy`` is ``(T, 17, 2)``, ``conf`` is ``(T, 17)``. Returns ``(T, 2)``.
    Frames where the weighted sum has no usable keypoints become NaN.
    """
    com = np.full((xy.shape[0], 2), np.nan, dtype=np.float32)
    for t in range(xy.shape[0]):
        wsum = 0.0
        accum = np.zeros(2, dtype=np.float32)
        for _, (idxs, mass) in T.ANTHROPOMETRIC_WEIGHTS.items():
            usable = [i for i in idxs if conf[t, i] >= min_conf]
            if not usable:
                continue
            seg_xy = xy[t, usable, :].mean(axis=0)
            accum += seg_xy * mass
            wsum += mass
        if wsum > 0:
            com[t] = accum / wsum
    return com


def _materialize_tracks(
    sparse: dict[int, dict[int, tuple[np.ndarray, np.ndarray]]],
    n_frames: int,
) -> dict[int, PoseTrack]:
    out: dict[int, PoseTrack] = {}
    for tid, frames in sparse.items():
        xy = np.full((n_frames, N_KP, 2), np.nan, dtype=np.float32)
        conf = np.zeros((n_frames, N_KP), dtype=np.float32)
        for f_idx, (k_xy, k_conf) in frames.items():
            xy[f_idx] = k_xy
            conf[f_idx] = k_conf
        com = estimate_com(xy, conf)
        out[tid] = PoseTrack(track_id=tid, xy=xy, conf=conf, com_xy=com)
    return out


def _save_cache(path: Path, tracks: dict[int, PoseTrack], n_frames: int) -> None:
    ids = np.array(sorted(tracks.keys()), dtype=np.int32)
    if ids.size == 0:
        np.savez_compressed(
            path,
            track_ids=ids,
            xy=np.zeros((0, n_frames, N_KP, 2), dtype=np.float32),
            conf=np.zeros((0, n_frames, N_KP), dtype=np.float32),
            com_xy=np.zeros((0, n_frames, 2), dtype=np.float32),
        )
        return
    stacked_xy = np.stack([tracks[int(i)].xy for i in ids])
    stacked_conf = np.stack([tracks[int(i)].conf for i in ids])
    stacked_com = np.stack([tracks[int(i)].com_xy for i in ids])
    np.savez_compressed(
        path, track_ids=ids, xy=stacked_xy, conf=stacked_conf, com_xy=stacked_com
    )


__all__ = [
    "N_KP",
    "PoseTrack",
    "run_pose",
    "load_pose_cache",
    "pick_climber_track",
    "estimate_com",
]
