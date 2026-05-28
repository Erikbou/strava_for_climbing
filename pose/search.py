"""User-facing movement-section search.

Query a section of one climb (by clip + time) and get the most similar sections
across the whole dataset, ranked. Thin layer over `similarity.SectionIndex`.

    # list what's indexed
    uv run --no-sync python -m pose.search --list
    # find sections similar to IMG_7952 @ 12.5s, render top hit side-by-side
    uv run --no-sync python -m pose.search --clip IMG_7952 --time 12.5 --k 5 --video
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .similarity import SectionIndex, load_index


def window_at(idx: SectionIndex, clip: str, t: float) -> int:
    """Index of the window covering time `t` in `clip` (nearest by center if none)."""
    same = [(i, m) for i, m in enumerate(idx.meta) if m["clip"] == clip]
    if not same:
        clips = sorted({m["clip"] for m in idx.meta})
        raise SystemExit(f"clip '{clip}' not found. available: {clips}")
    for i, m in same:
        if m["t0"] <= t < m["t1"]:
            return i
    return min(same, key=lambda im: abs((im[1]["t0"] + im[1]["t1"]) / 2 - t))[0]


def query(
    idx: SectionIndex, clip: str, t: float, *, k: int = 5, cross_clip: bool = True
) -> tuple[int, list[tuple[int, float]]]:
    q = window_at(idx, clip, t)
    return q, idx.search(q, k=k, same_clip=not cross_clip)


def _print_list(idx: SectionIndex) -> None:
    from collections import defaultdict

    by_clip: dict[str, list[dict]] = defaultdict(list)
    for m in idx.meta:
        by_clip[m["clip"]].append(m)
    print(f"{len(by_clip)} clip(s), {len(idx.meta)} sections:")
    for clip in sorted(by_clip):
        ms = by_clip[clip]
        print(f"  {clip:<28} {len(ms):>3} sections  0.0-{max(m['t1'] for m in ms):.1f}s")


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="Movement-section similarity search")
    p.add_argument("--keypoints", default=str(repo / "clips" / "keypoints"))
    p.add_argument("--clip", help="query clip stem")
    p.add_argument("--time", type=float, help="seconds into --clip")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--within-clip", action="store_true", help="allow matches in the same clip")
    p.add_argument("--list", action="store_true", help="list indexed clips/sections and exit")
    p.add_argument("--video", action="store_true", help="render side-by-side of the top hit")
    args = p.parse_args()

    idx = load_index(args.keypoints)
    if args.list or args.clip is None or args.time is None:
        _print_list(idx)
        if args.clip is None or args.time is None:
            return

    n_clips = len({m["clip"] for m in idx.meta})
    cross = not args.within_clip and n_clips > 1
    q, hits = query(idx, args.clip, args.time, k=args.k, cross_clip=cross)
    mq = idx.meta[q]
    print(f"\nquery [{mq['clip']}] {mq['t0']:.1f}-{mq['t1']:.1f}s  "
          f"({'cross-clip' if cross else 'within-clip'})")
    for rank, (j, sim) in enumerate(hits, 1):
        mj = idx.meta[j]
        print(f"  #{rank}  [{mj['clip']}] {mj['t0']:.1f}-{mj['t1']:.1f}s   cos={sim:.3f}")

    if args.video and hits:
        from .retrieval_video import render

        out = repo / "clips" / "retrieval" / f"{mq['clip']}_{mq['t0']:.0f}s.mp4"
        render(repo, idx, q, hits[0][0], hits[0][1], out)


if __name__ == "__main__":
    main()
