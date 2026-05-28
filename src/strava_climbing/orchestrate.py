"""Top-level batch pipeline: walk ``video`` rows and run pose → boundaries → metrics → overlay.

Stage 2 is intentionally out of this orchestrator — when enabled it will hook
in via ``routes/`` modules that are lazy-imported in ``run_stage2()``.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from . import body_stats, highlight, manifests
from .boundary_detection import find_attempts
from .config import paths as P
from .config import runtime as R
from .db import (
    connect,
    init_db,
    upsert_attempt,
    upsert_climber,
    upsert_route,
)
from .metrics import compute_metrics, compute_route_percentiles, current_config_hash
from .overlay import OverlayHUD, render_overlay
from .pose import load_pose_cache, pick_climber_track
from .provenance import RouteSource
from .schema import Attempt, Route

log = logging.getLogger("strava_climbing.orchestrate")


@dataclass(slots=True, frozen=True)
class CuratedRow:
    source_filename: str
    climber_name: str
    route_name: str
    gym: str
    color: str | None = None


def read_curated_csv(path: Path) -> dict[str, CuratedRow]:
    """Read ``data/curated_subset.csv``. Keyed by source_filename for fast lookup."""
    out: dict[str, CuratedRow] = {}
    if not path.exists():
        return out
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            r = CuratedRow(
                source_filename=row["source_filename"].strip(),
                climber_name=row["climber_name"].strip(),
                route_name=row["route_name"].strip(),
                gym=row["gym"].strip(),
                color=(row.get("color") or "").strip() or None,
            )
            out[r.source_filename] = r
    return out


def process_all(*, force: bool = False) -> dict:
    """Run the full Stage-1 pipeline across all successfully ingested videos."""
    P.ensure_dirs()
    init_db()

    curated = read_curated_csv(P.DATA_ROOT / "curated_subset.csv")
    cfg_hash = current_config_hash()
    stats = {"videos": 0, "attempts": 0, "skipped": 0, "errored": 0}

    with connect() as conn:
        videos = conn.execute(
            "SELECT id, source_path, normalized_path, height, fps "
            "FROM video WHERE ingest_status = 'ok'"
        ).fetchall()

        for v in videos:
            stats["videos"] += 1
            try:
                added = _process_one(
                    conn, dict(v), curated=curated, cfg_hash=cfg_hash, force=force
                )
                stats["attempts"] += added
            except Exception as e:
                log.exception("processing failed for video %s", v["id"])
                stats["errored"] += 1
                manifests.write(
                    manifests.Manifest(
                        stage="pose",
                        video_id=v["id"],
                        status="error",
                        inputs_hash=cfg_hash,
                        started_at=manifests.stamp(),
                        finished_at=manifests.stamp(),
                        error=str(e),
                    )
                )

        _finalize_smoothness_percentiles(conn, cfg_hash)

    if R.stage2_enabled():
        try:
            run_stage2()
        except ImportError as e:
            log.warning("stage 2 disabled (missing deps): %s", e)
        except Exception:
            log.exception("stage 2 errored — Stage-1 results preserved")

    return stats


def _process_one(
    conn,
    video: dict,
    *,
    curated: dict[str, CuratedRow],
    cfg_hash: str,
    force: bool,
) -> int:
    source_name = Path(video["source_path"]).name
    crow = curated.get(source_name)
    climber_id = upsert_climber(conn, crow.climber_name) if crow else None
    route_id = _resolve_route_from_curated(conn, crow) if crow else None
    return process_one_video(
        conn, video,
        climber_id=climber_id,
        route_id=route_id,
        climber_name=crow.climber_name if crow else None,
        cfg_hash=cfg_hash, force=force,
    )


def process_one_video(
    conn,
    video: dict,
    *,
    climber_id: int | None,
    route_id: int | None,
    climber_name: str | None,
    cfg_hash: str,
    force: bool = False,
) -> int:
    """Run pose → boundaries → metrics → stats → overlay → highlight for one video.

    Returns the number of attempts written. Idempotent on (video_id, cfg_hash)
    via the manifest unless ``force=True``.
    """
    video_id = video["id"]
    normalized = Path(video["normalized_path"])
    frame_h = int(video["height"])
    fps = float(video["fps"])

    if not force and manifests.is_complete(video_id, "metrics", cfg_hash):
        return 0

    # --- Pose stage -------------------------------------------------------------
    cache_path = P.POSE_CACHE_DIR / f"{normalized.stem}.npz"
    if force or not manifests.is_complete(video_id, "pose", cfg_hash):
        _run_pose_stage(video_id, normalized, cache_path, cfg_hash)

    tracks = load_pose_cache(cache_path)
    climber_track_id = pick_climber_track(tracks)
    if climber_track_id is None:
        log.warning("no climber track found for video %s", video_id)
        return 0
    track = tracks[climber_track_id]

    # --- Boundaries + metrics ---------------------------------------------------
    attempts = find_attempts(track.com_xy, track.xy, track.conf, frame_h)
    if not attempts:
        return 0

    route_source = RouteSource.MANUAL if route_id else RouteSource.UNASSIGNED

    added = 0
    for i, bounds in enumerate(attempts):
        metrics = compute_metrics(
            bounds, track.com_xy, fps=fps, attempts_count=len(attempts)
        )
        stats = body_stats.compute(
            bounds, track.xy, track.com_xy, fps=fps, frame_height=frame_h,
        )

        overlay_path = P.OVERLAYS_DIR / f"{video_id}_a{i}.mp4"
        try:
            render_overlay(
                normalized, track, bounds,
                OverlayHUD(
                    time_seconds=metrics.time_seconds,
                    smoothness_pct=None,  # filled later by _finalize_smoothness_percentiles
                    send=metrics.send,
                    climber_name=climber_name,
                ),
                overlay_path,
            )
        except Exception:
            log.exception("overlay render failed for video %s attempt %s", video_id, i)
            overlay_path = None

        highlight_path: Path | None = P.OVERLAYS_DIR.parent / "highlights" / f"{video_id}_a{i}.mp4"
        try:
            start_s, dur_s = highlight.pick_highlight_window(bounds, track.com_xy, fps=fps)
            highlight.render_highlight(
                normalized, highlight_path,
                start_seconds=start_s, duration_seconds=dur_s,
            )
        except Exception:
            log.exception("highlight render failed for video %s attempt %s", video_id, i)
            highlight_path = None

        upsert_attempt(
            conn,
            Attempt(
                id=None,
                video_id=video_id,
                climber_id=climber_id,
                route_id=route_id,
                start_frame=bounds.start_frame,
                end_frame=bounds.end_frame,
                time_seconds=metrics.time_seconds,
                smoothness_raw=metrics.smoothness_raw,
                smoothness_pct=None,
                send=metrics.send,
                attempts_count=metrics.attempts_count,
                route_source=route_source,
                overlay_path=str(overlay_path) if overlay_path else None,
                highlight_path=str(highlight_path) if highlight_path else None,
                dynamic_moves=stats.dynamic_moves,
                longest_reach_px=stats.longest_reach_px,
                hang_time_seconds=stats.hang_time_seconds,
                idle_seconds=stats.idle_seconds,
                config_hash=cfg_hash,
            ),
        )
        added += 1

    manifests.write(
        manifests.Manifest(
            stage="metrics",
            video_id=video_id,
            status="ok",
            inputs_hash=cfg_hash,
            started_at=manifests.stamp(),
            finished_at=manifests.stamp(),
            outputs=[str(P.OVERLAYS_DIR / f"{video_id}_a{i}.mp4") for i in range(added)],
        )
    )
    return added


def upsert_route_for(conn, *, gym: str, color: str | None) -> int:
    """Find-or-create a route keyed by (gym, color). Returns route id."""
    wall_row = conn.execute(
        "SELECT id FROM wall WHERE gym_name = %s", (gym,)
    ).fetchone()
    if wall_row is None:
        wall_id = conn.execute(
            "INSERT INTO wall(gym_name) VALUES (%s) RETURNING id", (gym,)
        ).fetchone()["id"]
    else:
        wall_id = wall_row["id"]

    row = conn.execute(
        "SELECT id FROM route WHERE wall_id = %s AND color IS NOT DISTINCT FROM %s",
        (wall_id, color),
    ).fetchone()
    if row is not None:
        return row["id"]
    return upsert_route(
        conn,
        Route(id=None, wall_id=wall_id, color=color, origin=RouteSource.MANUAL),
    )


def process_uploaded_file(
    raw_path: Path,
    *,
    climber_name: str,
    color: str | None,
    gym: str,
) -> int | None:
    """Ingest one uploaded video and run the full pipeline on it.

    Returns the attempt id of the first attempt extracted, or None if pose
    found no climber track (rare on a real climb clip; usually means the
    file isn't a climb video).
    """
    from .ingest import _detect_videotoolbox, _ingest_one

    P.ensure_dirs()
    init_db()
    cfg_hash = current_config_hash()
    use_vt = _detect_videotoolbox()

    with connect() as conn:
        entry = _ingest_one(conn, raw_path, use_vt)
        if entry.status not in ("ok", "skipped"):
            raise RuntimeError(f"ingest failed: {entry.reason}")
        # _ingest_one upserts the video; look it up by SHA.
        v_row = conn.execute(
            "SELECT id, source_path, normalized_path, height, fps "
            "FROM video WHERE source_sha256 = %s",
            (entry.source_sha256,),
        ).fetchone()
        if v_row is None:
            raise RuntimeError("video row missing after ingest")

        climber_id = upsert_climber(conn, climber_name)
        route_id = upsert_route_for(conn, gym=gym, color=color)

        process_one_video(
            conn, dict(v_row),
            climber_id=climber_id,
            route_id=route_id,
            climber_name=climber_name,
            cfg_hash=cfg_hash,
            force=True,
        )
        _finalize_smoothness_percentiles(conn, cfg_hash)

        row = conn.execute(
            "SELECT id FROM attempt WHERE video_id = %s ORDER BY id ASC LIMIT 1",
            (v_row["id"],),
        ).fetchone()
        return row["id"] if row else None


def _run_pose_stage(video_id: int, normalized: Path, cache_path: Path, cfg_hash: str) -> None:
    started = manifests.stamp()
    try:
        from .pose import run_pose  # lazy import — ultralytics is heavy

        run_pose(normalized, cache_path=cache_path)
    except Exception as e:
        manifests.write(
            manifests.Manifest(
                stage="pose", video_id=video_id, status="error",
                inputs_hash=cfg_hash, started_at=started, finished_at=manifests.stamp(),
                error=str(e),
            )
        )
        raise
    manifests.write(
        manifests.Manifest(
            stage="pose", video_id=video_id, status="ok",
            inputs_hash=cfg_hash, started_at=started, finished_at=manifests.stamp(),
            outputs=[str(cache_path)],
        )
    )


def _resolve_route_from_curated(conn, crow: CuratedRow) -> int:
    """Find-or-create the (wall, route) pair for a curated CSV row."""
    return upsert_route_for(conn, gym=crow.gym, color=crow.color)


def _finalize_smoothness_percentiles(conn, cfg_hash: str) -> None:
    """Recompute per-route smoothness percentiles using the frozen baseline strategy."""
    routes = conn.execute("SELECT DISTINCT route_id FROM attempt WHERE route_id IS NOT NULL").fetchall()
    for row in routes:
        route_id = row["route_id"]
        attempts = conn.execute(
            "SELECT id, smoothness_raw FROM attempt "
            "WHERE route_id = %s AND smoothness_raw IS NOT NULL "
            "ORDER BY id ASC",
            (route_id,),
        ).fetchall()
        raws = [r["smoothness_raw"] for r in attempts]
        pcts = compute_route_percentiles(raws)
        for r, pct in zip(attempts, pcts, strict=True):
            conn.execute(
                "UPDATE attempt SET smoothness_pct = %s WHERE id = %s",
                (pct, r["id"]),
            )


def run_stage2() -> None:
    """Hold detection + route auto-matching. Lazy-imports the ``routes`` package
    so a missing transformers / torch install does not break Stage 1.
    """
    from .routes import match  # noqa: F401 — TODO: implement in Stage 2
    raise NotImplementedError("Stage 2 not yet implemented")


def verify_demo() -> list[str]:
    """Walk the DB and stat() every referenced overlay path. Returns missing paths."""
    missing: list[str] = []
    with connect(read_only=True) as conn:
        for row in conn.execute(
            "SELECT id, overlay_path FROM attempt WHERE overlay_path IS NOT NULL"
        ).fetchall():
            if not Path(row["overlay_path"]).exists():
                missing.append(row["overlay_path"])
        for row in conn.execute(
            "SELECT id, sample_frame_path FROM route WHERE sample_frame_path IS NOT NULL"
        ).fetchall():
            if not Path(row["sample_frame_path"]).exists():
                missing.append(row["sample_frame_path"])
    return missing


__all__ = [
    "CuratedRow",
    "process_all",
    "process_one_video",
    "process_uploaded_file",
    "read_curated_csv",
    "upsert_route_for",
    "verify_demo",
]
