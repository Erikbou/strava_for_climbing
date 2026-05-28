"""Top-level batch pipeline: walk ``video`` rows and run pose → boundaries → metrics → overlay.

Stage 2 is intentionally out of this orchestrator — when enabled it will hook
in via ``routes/`` modules that are lazy-imported in ``run_stage2()``.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from . import db, manifests
from .boundary_detection import find_attempts
from .config import paths as P
from .config import runtime as R
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
    db.init_db()

    curated = read_curated_csv(P.DATA_ROOT / "curated_subset.csv")
    cfg_hash = current_config_hash()
    stats = {"videos": 0, "attempts": 0, "skipped": 0, "errored": 0}

    for v in db.list_ok_videos():
        stats["videos"] += 1
        try:
            added = _process_one(v, curated=curated, cfg_hash=cfg_hash, force=force)
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

    _finalize_smoothness_percentiles()

    if R.stage2_enabled():
        try:
            run_stage2()
        except ImportError as e:
            log.warning("stage 2 disabled (missing deps): %s", e)
        except Exception:
            log.exception("stage 2 errored — Stage-1 results preserved")

    return stats


def _process_one(
    video: dict,
    *,
    curated: dict[str, CuratedRow],
    cfg_hash: str,
    force: bool,
) -> int:
    video_id = video["id"]
    normalized_key = video["normalized_path"]
    normalized = db.normalized_local_path(normalized_key)
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

    # Climber + route resolution from the curated CSV (filename match).
    source_name = Path(video["source_path"]).name
    crow = curated.get(source_name)
    climber_id = db.upsert_climber(crow.climber_name) if crow else None
    route_id = _resolve_route(crow) if crow else None

    added = 0
    for i, bounds in enumerate(attempts):
        metrics = compute_metrics(
            bounds, track.com_xy, fps=fps, attempts_count=len(attempts)
        )
        overlay_local = P.OVERLAYS_DIR / f"{video_id}_a{i}.mp4"
        overlay_key: str | None = None
        try:
            render_overlay(
                normalized, track, bounds,
                OverlayHUD(
                    time_seconds=metrics.time_seconds,
                    smoothness_pct=None,  # filled later by _finalize_smoothness_percentiles
                    send=metrics.send,
                    climber_name=crow.climber_name if crow else None,
                ),
                overlay_local,
            )
        except Exception:
            log.exception("overlay render failed for video %s attempt %s", video_id, i)
        else:
            try:
                overlay_key = db.upload_overlay(overlay_local)
            except Exception as e:
                log.warning("overlay upload failed for %s: %s — using basename", overlay_local, e)
                overlay_key = overlay_local.name

        db.upsert_attempt(
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
                route_source=RouteSource.MANUAL if route_id else RouteSource.UNASSIGNED,
                overlay_path=overlay_key,
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


def _resolve_route(crow: CuratedRow) -> int:
    """Find-or-create the (wall, route) pair for a curated row."""
    wall_id = db.find_or_create_wall(crow.gym)
    existing = db.find_route(wall_id, crow.color)
    if existing is not None:
        return existing
    return db.upsert_route(
        Route(
            id=None, wall_id=wall_id, color=crow.color,
            origin=RouteSource.MANUAL,
            sample_frame_path=None, hold_layout=None,
            layout_embedding=None, cluster_confidence=None,
        ),
    )


def _finalize_smoothness_percentiles() -> None:
    """Recompute per-route smoothness percentiles using the frozen baseline strategy."""
    for route_id in db.distinct_route_ids_with_attempts():
        attempts = db.attempts_for_route(route_id)
        raws = [r["smoothness_raw"] for r in attempts]
        pcts = compute_route_percentiles(raws)
        for r, pct in zip(attempts, pcts, strict=True):
            db.update_attempt_smoothness_pct(r["id"], pct)


def run_stage2() -> None:
    """Hold detection + route auto-matching. Lazy-imports the ``routes`` package
    so a missing transformers / torch install does not break Stage 1.
    """
    from .routes import match  # noqa: F401 — TODO: implement in Stage 2
    raise NotImplementedError("Stage 2 not yet implemented")


def verify_demo() -> list[str]:
    """Check every overlay / sample frame referenced by the DB.

    In Supabase mode this hits the Storage API; in SQLite mode it stats local
    files. Returns the list of missing keys/paths.
    """
    missing: list[str] = []
    for key in db.overlay_paths_in_use():
        if not db.overlay_exists(key):
            missing.append(key)
    for frame in db.route_sample_frame_paths():
        if not Path(frame).exists():
            missing.append(frame)
    return missing


__all__ = ["CuratedRow", "process_all", "read_curated_csv", "verify_demo"]
