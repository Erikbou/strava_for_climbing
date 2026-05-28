#!/usr/bin/env python3
"""End-to-end pose pipeline: transcode -> extract -> visualize -> analytics.

Example:
    .venv/bin/python run.py --video ../IMG_7952.MOV
"""

from __future__ import annotations

import argparse
import os
import time

from pose.extract import transcode, extract_pose
from pose.visualize import render_overlay
from pose.analytics import plot_analytics
from pose.schema import MovementSequence

REPO_DIR = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    p = argparse.ArgumentParser(description="Climb pose visualization pipeline")
    p.add_argument("--video", default=os.path.join(REPO_DIR, "..", "IMG_7952.MOV"))
    p.add_argument("--out", default=os.path.join(REPO_DIR, "output"))
    p.add_argument("--model", default=os.path.join(REPO_DIR, "models", "pose_landmarker_heavy.task"))
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--max-dim", type=int, default=1280)
    args = p.parse_args()

    os.makedirs(args.out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.video))[0]
    work = os.path.join(args.out, "work.mp4")

    t0 = time.time()
    print(f"[1/4] transcoding {args.video} -> {work} ({args.max_dim}px, {args.fps}fps)")
    transcode(args.video, work, max_dim=args.max_dim, fps=args.fps)

    print("[2/4] extracting pose")
    seq = extract_pose(work, args.model)
    npz = os.path.join(args.out, "keypoints.npz")
    js = os.path.join(args.out, "keypoints.json")
    seq.save_npz(npz)
    seq.save_json(js)
    print(f"  saved {seq.num_frames} frames -> {npz}, {js}")

    print("[3/4] rendering skeleton overlay")
    overlay = os.path.join(args.out, f"{stem}_pose.mp4")
    render_overlay(seq, work, overlay)
    print(f"  saved {overlay}")

    print("[4/4] computing analytics")
    chart = os.path.join(args.out, "analytics.png")
    plot_analytics(seq, chart)
    print(f"  saved {chart}")

    print(f"done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
