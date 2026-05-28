"""Batch MediaPipe keypoint extraction for the section-search dataset.

For every video in an input dir, transcode + run pose extraction and save one
`keypoints.npz` (MovementSequence) per clip. Run in the isolated mediapipe env:

    uv run --no-project --with mediapipe --with opencv-python --with numpy \
        python -m pose.extract_batch
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from .extract import extract_pose, transcode

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}


def extract_clip(video: Path, out_npz: Path, model: Path, *, max_dim: int = 1280, fps: int = 30) -> None:
    out_npz.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "work.mp4"
        transcode(str(video), str(work), max_dim=max_dim, fps=fps)
        seq = extract_pose(str(work), str(model))
    seq.save_npz(str(out_npz))
    print(f"  {video.name}: {seq.num_frames} frames -> {out_npz}")


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="Batch-extract MediaPipe keypoints per clip")
    p.add_argument("--in-dir", default=str(repo / "data" / "raw"))
    p.add_argument("--out-dir", default=str(repo / "clips" / "keypoints"))
    p.add_argument("--model", default=str(repo / "models" / "pose_landmarker_heavy.task"))
    p.add_argument("--force", action="store_true", help="re-extract even if npz exists")
    args = p.parse_args()

    in_dir, out_dir = Path(args.in_dir), Path(args.out_dir)
    vids = sorted(v for v in in_dir.iterdir() if v.suffix.lower() in VIDEO_EXTS)
    if not vids:
        print(f"no videos in {in_dir}")
        return
    print(f"extracting {len(vids)} clip(s) from {in_dir}")
    for v in vids:
        out_npz = out_dir / f"{v.stem}.npz"
        if out_npz.exists() and not args.force:
            print(f"  {v.name}: cached, skipping")
            continue
        extract_clip(v, out_npz, Path(args.model))


if __name__ == "__main__":
    main()
