"""Offline backend: SQLite + local filesystem.

Activated when no Supabase URL is configured (or when
``STRAVA_CLIMBING_BACKEND=sqlite`` is set). Everything lives under
``DATA_ROOT`` — schema, attempts, and the .mp4 renders themselves.

DB columns ``video.normalized_path`` and ``attempt.overlay_path`` carry the
**basename only** (e.g., ``abc123def456.mp4``), matching the Supabase
backend so callers can stay backend-agnostic. ``normalized_local_path()`` /
``overlay_local_path()`` resolve those keys to absolute paths under
``data/normalized/`` and ``data/overlays/``.
"""

from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import paths as P
from .provenance import RouteSource  # re-exported below
from .schema import Attempt, Route, Video

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS climber (
  id      INTEGER PRIMARY KEY,
  name    TEXT NOT NULL,
  aliases TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(aliases)),
  UNIQUE (name COLLATE NOCASE)
);

CREATE TABLE IF NOT EXISTS video (
  id               INTEGER PRIMARY KEY,
  source_path      TEXT NOT NULL,
  normalized_path  TEXT NOT NULL UNIQUE,
  source_sha256    TEXT NOT NULL UNIQUE,
  duration_seconds REAL NOT NULL CHECK (duration_seconds > 0),
  width            INTEGER NOT NULL CHECK (width  > 0),
  height           INTEGER NOT NULL CHECK (height > 0),
  fps              REAL    NOT NULL CHECK (fps    > 0),
  ingest_status    TEXT NOT NULL CHECK (ingest_status IN ('pending','ok','rejected','error')),
  ingest_report    TEXT    CHECK (ingest_report IS NULL OR json_valid(ingest_report))
);

CREATE TABLE IF NOT EXISTS wall (
  id                INTEGER PRIMARY KEY,
  gym_name          TEXT NOT NULL,
  sample_frame_path TEXT,
  dinov3_embedding  BLOB
);

CREATE TABLE IF NOT EXISTS route (
  id                 INTEGER PRIMARY KEY,
  wall_id            INTEGER NOT NULL REFERENCES wall(id) ON DELETE RESTRICT,
  color              TEXT,
  sample_frame_path  TEXT,
  hold_layout        TEXT CHECK (hold_layout IS NULL OR json_valid(hold_layout)),
  layout_embedding   BLOB,
  origin             TEXT NOT NULL CHECK (origin IN ('manual','auto','unassigned')),
  cluster_confidence REAL CHECK (cluster_confidence IS NULL
                                 OR cluster_confidence BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS attempt (
  id              INTEGER PRIMARY KEY,
  climber_id      INTEGER REFERENCES climber(id) ON DELETE SET NULL,
  route_id        INTEGER REFERENCES route(id)   ON DELETE SET NULL,
  video_id        INTEGER NOT NULL REFERENCES video(id) ON DELETE CASCADE,
  start_frame     INTEGER NOT NULL CHECK (start_frame >= 0),
  end_frame       INTEGER NOT NULL CHECK (end_frame > start_frame),
  time_seconds    REAL    NOT NULL CHECK (time_seconds > 0),
  smoothness_raw  REAL,
  smoothness_pct  REAL CHECK (smoothness_pct IS NULL OR smoothness_pct BETWEEN 0 AND 100),
  send            INTEGER NOT NULL CHECK (send IN (0,1)),
  attempts_count  INTEGER NOT NULL CHECK (attempts_count >= 1),
  route_source    TEXT NOT NULL CHECK (route_source IN ('manual','auto','unassigned')),
  overlay_path    TEXT UNIQUE,
  config_hash     TEXT NOT NULL,
  UNIQUE (video_id, start_frame, end_frame)
);

CREATE TABLE IF NOT EXISTS hold (
  id        INTEGER PRIMARY KEY,
  wall_id   INTEGER NOT NULL REFERENCES wall(id)  ON DELETE CASCADE,
  route_id  INTEGER          REFERENCES route(id) ON DELETE SET NULL,
  x REAL NOT NULL, y REAL NOT NULL, w REAL NOT NULL, h REAL NOT NULL,
  color_hsv TEXT CHECK (color_hsv IS NULL OR json_valid(color_hsv)),
  CHECK (x BETWEEN 0 AND 1 AND y BETWEEN 0 AND 1 AND w > 0 AND h > 0)
);

CREATE INDEX IF NOT EXISTS idx_attempt_route_send_time
  ON attempt(route_id, send DESC, time_seconds ASC);
CREATE INDEX IF NOT EXISTS idx_attempt_climber ON attempt(climber_id);
CREATE INDEX IF NOT EXISTS idx_attempt_video   ON attempt(video_id);
CREATE INDEX IF NOT EXISTS idx_route_origin    ON route(origin);
CREATE INDEX IF NOT EXISTS idx_route_wall      ON route(wall_id);
CREATE INDEX IF NOT EXISTS idx_hold_wall_route ON hold(wall_id, route_id);

CREATE TRIGGER IF NOT EXISTS trg_attempt_protect_manual
BEFORE UPDATE OF route_id, route_source ON attempt
FOR EACH ROW WHEN OLD.route_source = 'manual' AND NEW.route_source != 'manual'
BEGIN
  SELECT RAISE(ABORT, 'cannot overwrite manual route assignment');
END;
"""


def _db_path() -> Path:
    return P.DATA_ROOT / "climbing.sqlite"


def _connect_raw(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{path}", uri=True, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@lru_cache(maxsize=1)
def _conn() -> sqlite3.Connection:
    path = _db_path()
    conn = _connect_raw(path)
    conn.executescript(SCHEMA_SQL)
    return conn


def init_db() -> None:
    """Create the SQLite database and schema. Idempotent."""
    _conn()


# --- Writes ----------------------------------------------------------------


def upsert_climber(name: str, aliases: list[str] | None = None) -> int:
    aliases_json = json.dumps(aliases or [])
    cur = _conn().execute(
        "INSERT INTO climber(name, aliases) VALUES (?, ?) "
        "ON CONFLICT(name) DO UPDATE SET aliases = excluded.aliases "
        "RETURNING id",
        (name, aliases_json),
    )
    return cur.fetchone()[0]


def upsert_video(v: Video) -> int:
    cur = _conn().execute(
        """
        INSERT INTO video(source_path, normalized_path, source_sha256,
                          duration_seconds, width, height, fps,
                          ingest_status, ingest_report)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_sha256) DO UPDATE SET
            normalized_path = excluded.normalized_path,
            ingest_status   = excluded.ingest_status,
            ingest_report   = excluded.ingest_report
        RETURNING id
        """,
        (
            v.source_path,
            v.normalized_path,
            v.source_sha256,
            v.duration_seconds,
            v.width,
            v.height,
            v.fps,
            v.ingest_status,
            json.dumps(v.ingest_report) if v.ingest_report else None,
        ),
    )
    return cur.fetchone()[0]


def get_video_by_sha(sha256: str) -> Video | None:
    row = _conn().execute(
        "SELECT * FROM video WHERE source_sha256 = ?", (sha256,)
    ).fetchone()
    if row is None:
        return None
    return Video(
        id=row["id"],
        source_path=row["source_path"],
        normalized_path=row["normalized_path"],
        source_sha256=row["source_sha256"],
        duration_seconds=row["duration_seconds"],
        width=row["width"],
        height=row["height"],
        fps=row["fps"],
        ingest_status=row["ingest_status"],
        ingest_report=json.loads(row["ingest_report"]) if row["ingest_report"] else None,
    )


def upsert_attempt(a: Attempt) -> int:
    cur = _conn().execute(
        """
        INSERT INTO attempt(climber_id, route_id, video_id,
                            start_frame, end_frame, time_seconds,
                            smoothness_raw, smoothness_pct,
                            send, attempts_count, route_source,
                            overlay_path, config_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_id, start_frame, end_frame) DO UPDATE SET
            climber_id     = excluded.climber_id,
            route_id       = excluded.route_id,
            time_seconds   = excluded.time_seconds,
            smoothness_raw = excluded.smoothness_raw,
            smoothness_pct = excluded.smoothness_pct,
            send           = excluded.send,
            attempts_count = excluded.attempts_count,
            overlay_path   = excluded.overlay_path,
            config_hash    = excluded.config_hash
        RETURNING id
        """,
        (
            a.climber_id,
            a.route_id,
            a.video_id,
            a.start_frame,
            a.end_frame,
            a.time_seconds,
            a.smoothness_raw,
            a.smoothness_pct,
            int(a.send),
            a.attempts_count,
            str(a.route_source),
            a.overlay_path,
            a.config_hash,
        ),
    )
    return cur.fetchone()[0]


def upsert_route(r: Route) -> int:
    cur = _conn().execute(
        """
        INSERT INTO route(wall_id, color, sample_frame_path, hold_layout,
                          layout_embedding, origin, cluster_confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        (
            r.wall_id,
            r.color,
            r.sample_frame_path,
            json.dumps(r.hold_layout) if r.hold_layout else None,
            r.layout_embedding,
            str(r.origin),
            r.cluster_confidence,
        ),
    )
    return cur.fetchone()[0]


def update_attempt_smoothness_pct(attempt_id: int, smoothness_pct: float | None) -> None:
    _conn().execute(
        "UPDATE attempt SET smoothness_pct = ? WHERE id = ?",
        (smoothness_pct, attempt_id),
    )


def find_or_create_wall(gym_name: str) -> int:
    row = _conn().execute("SELECT id FROM wall WHERE gym_name = ?", (gym_name,)).fetchone()
    if row is not None:
        return row["id"]
    return _conn().execute(
        "INSERT INTO wall(gym_name) VALUES (?) RETURNING id", (gym_name,)
    ).fetchone()[0]


def find_route(wall_id: int, color: str | None) -> int | None:
    row = _conn().execute(
        "SELECT id FROM route WHERE wall_id = ? AND color IS ?", (wall_id, color)
    ).fetchone()
    return row["id"] if row else None


# --- Reads -----------------------------------------------------------------


def list_ok_videos() -> list[dict[str, Any]]:
    rows = _conn().execute(
        "SELECT id, source_path, normalized_path, height, fps "
        "FROM video WHERE ingest_status = 'ok'"
    ).fetchall()
    return [dict(r) for r in rows]


def attempts_for_route(route_id: int) -> list[dict[str, Any]]:
    rows = _conn().execute(
        "SELECT id, smoothness_raw FROM attempt "
        "WHERE route_id = ? AND smoothness_raw IS NOT NULL "
        "ORDER BY id ASC",
        (route_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def distinct_route_ids_with_attempts() -> list[int]:
    rows = _conn().execute(
        "SELECT DISTINCT route_id FROM attempt WHERE route_id IS NOT NULL"
    ).fetchall()
    return [r["route_id"] for r in rows]


def leaderboard(route_id: int) -> list[dict[str, Any]]:
    rows = _conn().execute(
        """
        SELECT a.id            AS attempt_id,
               c.name          AS climber_name,
               a.time_seconds  AS time_seconds,
               a.smoothness_pct AS smoothness_pct,
               a.send          AS send,
               a.overlay_path  AS overlay_path,
               a.attempts_count AS attempts_count
          FROM attempt a
          LEFT JOIN climber c ON c.id = a.climber_id
         WHERE a.route_id = ?
         ORDER BY a.send DESC, a.time_seconds ASC
        """,
        (route_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_routes() -> list[dict[str, Any]]:
    rows = _conn().execute(
        """
        SELECT r.id, r.color, r.origin, r.sample_frame_path,
               COUNT(a.id) AS attempt_count
          FROM route r
          LEFT JOIN attempt a ON a.route_id = r.id
         GROUP BY r.id
         ORDER BY attempt_count DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def overlay_paths_in_use() -> list[str]:
    rows = _conn().execute(
        "SELECT overlay_path FROM attempt WHERE overlay_path IS NOT NULL"
    ).fetchall()
    return [r["overlay_path"] for r in rows]


def route_sample_frame_paths() -> list[str]:
    rows = _conn().execute(
        "SELECT sample_frame_path FROM route WHERE sample_frame_path IS NOT NULL"
    ).fetchall()
    return [r["sample_frame_path"] for r in rows]


def get_attempt_detail(attempt_id: int) -> dict[str, Any] | None:
    row = _conn().execute(
        """
        SELECT a.*, c.name AS climber_name, r.color AS route_color,
               w.gym_name AS gym_name, v.normalized_path AS normalized_path
          FROM attempt a
          LEFT JOIN climber c ON c.id = a.climber_id
          LEFT JOIN route   r ON r.id = a.route_id
          LEFT JOIN wall    w ON w.id = r.wall_id
          LEFT JOIN video   v ON v.id = a.video_id
         WHERE a.id = ?
        """,
        (attempt_id,),
    ).fetchone()
    return dict(row) if row else None


def get_route_with_wall(route_id: int) -> dict[str, Any] | None:
    row = _conn().execute(
        "SELECT r.*, w.gym_name "
        "FROM route r JOIN wall w ON w.id = r.wall_id "
        "WHERE r.id = ?",
        (route_id,),
    ).fetchone()
    return dict(row) if row else None


# --- Storage (filesystem) --------------------------------------------------


def upload_normalized(local_path: Path) -> str:
    """No-op: the file is already on disk under data/normalized/."""
    return local_path.name


def upload_overlay(local_path: Path) -> str:
    return local_path.name


def normalized_local_path(key: str) -> Path:
    return P.NORMALIZED_DIR / key


def overlay_local_path(key: str) -> Path:
    return P.OVERLAYS_DIR / key


def overlay_playback_source(key: str) -> Path:
    return overlay_local_path(key)


def normalized_playback_source(key: str) -> Path:
    return normalized_local_path(key)


def overlay_exists(key: str) -> bool:
    return overlay_local_path(key).exists()


def normalized_exists(key: str) -> bool:
    return normalized_local_path(key).exists()


__all__ = [
    "RouteSource",
    "SCHEMA_SQL",
    "attempts_for_route",
    "distinct_route_ids_with_attempts",
    "find_or_create_wall",
    "find_route",
    "get_attempt_detail",
    "get_route_with_wall",
    "get_video_by_sha",
    "init_db",
    "leaderboard",
    "list_ok_videos",
    "list_routes",
    "normalized_exists",
    "normalized_local_path",
    "normalized_playback_source",
    "overlay_exists",
    "overlay_local_path",
    "overlay_paths_in_use",
    "overlay_playback_source",
    "route_sample_frame_paths",
    "update_attempt_smoothness_pct",
    "upload_normalized",
    "upload_overlay",
    "upsert_attempt",
    "upsert_climber",
    "upsert_route",
    "upsert_video",
]
