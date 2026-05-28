"""SQLite layer: connection factory, schema DDL, and thin repositories.

Every connection MUST go through `connect()` so that foreign keys, WAL, and
busy timeout are set. `init_db()` is idempotent. Read-only connections use
URI mode so the demo path can be opened with mode=ro and skip lock contention.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .provenance import RouteSource
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


def connect(path: str | Path, *, read_only: bool = False) -> sqlite3.Connection:
    """Open a connection with required pragmas. Always use this — never sqlite3.connect()."""
    p = str(path)
    uri = f"file:{p}?mode=ro" if read_only else f"file:{p}"
    conn = sqlite3.connect(uri, uri=True, isolation_level=None)  # autocommit; use BEGIN explicitly
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    fk_on = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk_on == 1, "foreign_keys pragma did not stick — check SQLite build"
    return conn


def init_db(path: str | Path) -> None:
    """Create tables/indexes/triggers if missing. Idempotent."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.executescript(SCHEMA_SQL)


# --- Repository helpers (thin) ----------------------------------------------


def upsert_climber(conn: sqlite3.Connection, name: str, aliases: list[str] | None = None) -> int:
    aliases_json = json.dumps(aliases or [])
    cur = conn.execute(
        "INSERT INTO climber(name, aliases) VALUES (?, ?) "
        "ON CONFLICT(name) DO UPDATE SET aliases = excluded.aliases "
        "RETURNING id",
        (name, aliases_json),
    )
    return cur.fetchone()[0]


def upsert_video(conn: sqlite3.Connection, v: Video) -> int:
    cur = conn.execute(
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


def get_video_by_sha(conn: sqlite3.Connection, sha256: str) -> Video | None:
    row = conn.execute("SELECT * FROM video WHERE source_sha256 = ?", (sha256,)).fetchone()
    return _row_to_video(row) if row else None


def upsert_attempt(conn: sqlite3.Connection, a: Attempt) -> int:
    cur = conn.execute(
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


def upsert_route(conn: sqlite3.Connection, r: Route) -> int:
    cur = conn.execute(
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


def leaderboard(conn: sqlite3.Connection, route_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
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


def list_routes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
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


def _row_to_video(row: sqlite3.Row) -> Video:
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


__all__ = [
    "SCHEMA_SQL",
    "RouteSource",
    "connect",
    "get_video_by_sha",
    "init_db",
    "leaderboard",
    "list_routes",
    "upsert_attempt",
    "upsert_climber",
    "upsert_route",
    "upsert_video",
]
