"""Render a query climbing section next to its top cross-clip match.

Builds the SectionIndex from clips/keypoints, finds the strongest cross-clip
window pair (or a user-specified query), cuts both sections from their source
videos, and hstacks them into one MP4 — a tangible "find similar move" demo.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np

from .similarity import load_index

_SRC_DIRS = ("clips/raw", "data/raw", "output")
_SRC_EXTS = (".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".MOV")


def resolve_source(repo: Path, stem: str) -> Path:
    for d in _SRC_DIRS:
        for ext in _SRC_EXTS:
            cand = repo / d / f"{stem}{ext}"
            if cand.exists():
                return cand
    raise SystemExit(f"no source video found for clip '{stem}' in {_SRC_DIRS}")


def best_cross_pair(idx) -> tuple[int, int, float]:
    """Globally strongest (query, match, cos) pair from different clips."""
    best = (-1, -1, -np.inf)
    for q in range(len(idx.meta)):
        hits = idx.search(q, k=1, same_clip=False)
        if hits and hits[0][1] > best[2]:
            best = (q, hits[0][0], hits[0][1])
    return best


def _cut(repo: Path, m: dict, out: Path) -> None:
    src = resolve_source(repo, m["clip"])
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(m["t0"]), "-t", str(round(m["t1"] - m["t0"], 3)),
         "-i", str(src), "-vf", "scale=-2:540,setsar=1", "-an", str(out)],
        check=True, capture_output=True,
    )


def render(repo: Path, idx, q: int, j: int, sim: float, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    a, b = out.with_suffix(".q.mp4"), out.with_suffix(".m.mp4")
    _cut(repo, idx.meta[q], a)
    _cut(repo, idx.meta[j], b)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(a), "-i", str(b),
         "-filter_complex", "[0:v][1:v]hstack=inputs=2", "-an", str(out)],
        check=True, capture_output=True,
    )
    a.unlink(missing_ok=True)
    b.unlink(missing_ok=True)
    mq, mj = idx.meta[q], idx.meta[j]
    print(f"query  [{mq['clip']}] {mq['t0']:.1f}-{mq['t1']:.1f}s")
    print(f"match  [{mj['clip']}] {mj['t0']:.1f}-{mj['t1']:.1f}s   cos={sim:.3f}")
    print(f"wrote {out}")


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="Side-by-side query/top-match retrieval video")
    p.add_argument("--keypoints", default=str(repo / "clips" / "keypoints"))
    p.add_argument("--out", default=str(repo / "clips" / "retrieval" / "match.mp4"))
    p.add_argument("--query-clip", help="clip stem to query from (default: globally best pair)")
    p.add_argument("--query-time", type=float, help="seconds into --query-clip")
    args = p.parse_args()

    idx = load_index(args.keypoints)
    if args.query_clip is not None and args.query_time is not None:
        cands = [i for i, m in enumerate(idx.meta)
                 if m["clip"] == args.query_clip and m["t0"] <= args.query_time < m["t1"]]
        if not cands:
            raise SystemExit(f"no window at {args.query_time}s in {args.query_clip}")
        q = cands[0]
        j, sim = idx.search(q, k=1, same_clip=False)[0]
    else:
        q, j, sim = best_cross_pair(idx)

    render(repo, idx, q, j, sim, Path(args.out))


if __name__ == "__main__":
    main()
