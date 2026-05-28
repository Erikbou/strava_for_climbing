"""Postgres layer: connection factory, schema DDL, and thin repositories.

Use `connect()` to get a configured psycopg connection. The DSN comes from
`DATABASE_URL` unless one is passed explicitly. `init_db()` is idempotent.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .provenance import RouteSource
from .schema import Attempt, Route, Video

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS climber (
  id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name    TEXT NOT NULL,
  aliases JSONB NOT NULL DEFAULT '[]'::jsonb
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_climber_name_ci ON climber (LOWER(name));

CREATE TABLE IF NOT EXISTS video (
  id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_path      TEXT NOT NULL,
  normalized_path  TEXT NOT NULL UNIQUE,
  source_sha256    TEXT NOT NULL UNIQUE,
  duration_seconds DOUBLE PRECISION NOT NULL CHECK (duration_seconds > 0),
  width            INTEGER NOT NULL CHECK (width  > 0),
  height           INTEGER NOT NULL CHECK (height > 0),
  fps              DOUBLE PRECISION NOT NULL CHECK (fps > 0),
  ingest_status    TEXT NOT NULL CHECK (ingest_status IN ('pending','ok','rejected','error')),
  ingest_report    JSONB
);

CREATE TABLE IF NOT EXISTS wall (
  id                INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  gym_name          TEXT NOT NULL,
  sample_frame_path TEXT,
  dinov3_embedding  BYTEA
);

CREATE TABLE IF NOT EXISTS route (
  id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  wall_id            INTEGER NOT NULL REFERENCES wall(id) ON DELETE RESTRICT,
  color              TEXT,
  sample_frame_path  TEXT,
  hold_layout        JSONB,
  layout_embedding   BYTEA,
  origin             TEXT NOT NULL CHECK (origin IN ('manual','auto','unassigned')),
  cluster_confidence DOUBLE PRECISION CHECK (cluster_confidence IS NULL
                                             OR cluster_confidence BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS attempt (
  id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  climber_id      INTEGER REFERENCES climber(id) ON DELETE SET NULL,
  route_id        INTEGER REFERENCES route(id)   ON DELETE SET NULL,
  video_id        INTEGER NOT NULL REFERENCES video(id) ON DELETE CASCADE,
  start_frame     INTEGER NOT NULL CHECK (start_frame >= 0),
  end_frame       INTEGER NOT NULL CHECK (end_frame > start_frame),
  time_seconds    DOUBLE PRECISION NOT NULL CHECK (time_seconds > 0),
  smoothness_raw  DOUBLE PRECISION,
  smoothness_pct  DOUBLE PRECISION CHECK (smoothness_pct IS NULL OR smoothness_pct BETWEEN 0 AND 100),
  send            BOOLEAN NOT NULL,
  attempts_count  INTEGER NOT NULL CHECK (attempts_count >= 1),
  route_source    TEXT NOT NULL CHECK (route_source IN ('manual','auto','unassigned')),
  overlay_path    TEXT UNIQUE,
  highlight_path  TEXT UNIQUE,
  dynamic_moves   INTEGER,
  longest_reach_px DOUBLE PRECISION,
  hang_time_seconds DOUBLE PRECISION,
  idle_seconds    DOUBLE PRECISION,
  posted_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  config_hash     TEXT NOT NULL,
  UNIQUE (video_id, start_frame, end_frame)
);

-- Additive migrations for upgrading an existing schema (Postgres >= 9.6).
ALTER TABLE attempt ADD COLUMN IF NOT EXISTS highlight_path    TEXT UNIQUE;
ALTER TABLE attempt ADD COLUMN IF NOT EXISTS dynamic_moves     INTEGER;
ALTER TABLE attempt ADD COLUMN IF NOT EXISTS longest_reach_px  DOUBLE PRECISION;
ALTER TABLE attempt ADD COLUMN IF NOT EXISTS hang_time_seconds DOUBLE PRECISION;
ALTER TABLE attempt ADD COLUMN IF NOT EXISTS idle_seconds      DOUBLE PRECISION;
ALTER TABLE attempt ADD COLUMN IF NOT EXISTS posted_at         TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_attempt_posted_at ON attempt(posted_at DESC);

CREATE TABLE IF NOT EXISTS hold (
  id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  wall_id   INTEGER NOT NULL REFERENCES wall(id)  ON DELETE CASCADE,
  route_id  INTEGER          REFERENCES route(id) ON DELETE SET NULL,
  x DOUBLE PRECISION NOT NULL, y DOUBLE PRECISION NOT NULL,
  w DOUBLE PRECISION NOT NULL, h DOUBLE PRECISION NOT NULL,
  color_hsv JSONB,
  CHECK (x BETWEEN 0 AND 1 AND y BETWEEN 0 AND 1 AND w > 0 AND h > 0)
);

CREATE INDEX IF NOT EXISTS idx_attempt_route_send_time
  ON attempt(route_id, send DESC, time_seconds ASC);
CREATE INDEX IF NOT EXISTS idx_attempt_climber ON attempt(climber_id);
CREATE INDEX IF NOT EXISTS idx_attempt_video   ON attempt(video_id);
CREATE INDEX IF NOT EXISTS idx_route_origin    ON route(origin);
CREATE INDEX IF NOT EXISTS idx_route_wall      ON route(wall_id);
CREATE INDEX IF NOT EXISTS idx_hold_wall_route ON hold(wall_id, route_id);

CREATE OR REPLACE FUNCTION trg_attempt_protect_manual_fn() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.route_source = 'manual' AND NEW.route_source <> 'manual' THEN
    RAISE EXCEPTION 'cannot overwrite manual route assignment';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_attempt_protect_manual ON attempt;
CREATE TRIGGER trg_attempt_protect_manual
BEFORE UPDATE OF route_id, route_source ON attempt
FOR EACH ROW EXECUTE FUNCTION trg_attempt_protect_manual_fn();
"""


def _resolve_dsn(dsn: str | Path | None) -> str:
    if dsn is not None:
        return str(dsn)
    env_dsn = os.environ.get("DATABASE_URL")
    if not env_dsn:
        raise RuntimeError(
            "DATABASE_URL is not set. Run inside `specific dev` / `specific exec`, "
            "or export DATABASE_URL manually."
        )
    return env_dsn


def connect(dsn: str | Path | None = None, *, read_only: bool = False) -> psycopg.Connection:
    """Open a psycopg connection with `dict_row` factory. `read_only` toggles a read-only txn."""
    conn = psycopg.connect(_resolve_dsn(dsn), row_factory=dict_row, autocommit=True)
    if read_only:
        conn.execute("SET default_transaction_read_only = on")
    return conn


def init_db(dsn: str | Path | None = None) -> None:
    """Create tables/indexes/triggers if missing. Idempotent."""
    with connect(dsn) as conn:
        conn.execute(SCHEMA_SQL)


# --- Repository helpers (thin) ----------------------------------------------


def upsert_climber(conn: psycopg.Connection, name: str, aliases: list[str] | None = None) -> int:
    aliases_json = json.dumps(aliases or [])
    cur = conn.execute(
        """
        INSERT INTO climber(name, aliases) VALUES (%s, %s::jsonb)
        ON CONFLICT ((LOWER(name))) DO UPDATE SET aliases = EXCLUDED.aliases
        RETURNING id
        """,
        (name, aliases_json),
    )
    return cur.fetchone()["id"]


def upsert_video(conn: psycopg.Connection, v: Video) -> int:
    cur = conn.execute(
        """
        INSERT INTO video(source_path, normalized_path, source_sha256,
                          duration_seconds, width, height, fps,
                          ingest_status, ingest_report)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT(source_sha256) DO UPDATE SET
            normalized_path = EXCLUDED.normalized_path,
            ingest_status   = EXCLUDED.ingest_status,
            ingest_report   = EXCLUDED.ingest_report
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
    return cur.fetchone()["id"]


def get_video_by_sha(conn: psycopg.Connection, sha256: str) -> Video | None:
    row = conn.execute(
        "SELECT * FROM video WHERE source_sha256 = %s", (sha256,)
    ).fetchone()
    return _row_to_video(row) if row else None


def upsert_attempt(conn: psycopg.Connection, a: Attempt) -> int:
    cur = conn.execute(
        """
        INSERT INTO attempt(climber_id, route_id, video_id,
                            start_frame, end_frame, time_seconds,
                            smoothness_raw, smoothness_pct,
                            send, attempts_count, route_source,
                            overlay_path, highlight_path,
                            dynamic_moves, longest_reach_px,
                            hang_time_seconds, idle_seconds,
                            config_hash)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(video_id, start_frame, end_frame) DO UPDATE SET
            climber_id        = EXCLUDED.climber_id,
            route_id          = EXCLUDED.route_id,
            time_seconds      = EXCLUDED.time_seconds,
            smoothness_raw    = EXCLUDED.smoothness_raw,
            smoothness_pct    = EXCLUDED.smoothness_pct,
            send              = EXCLUDED.send,
            attempts_count    = EXCLUDED.attempts_count,
            overlay_path      = EXCLUDED.overlay_path,
            highlight_path    = EXCLUDED.highlight_path,
            dynamic_moves     = EXCLUDED.dynamic_moves,
            longest_reach_px  = EXCLUDED.longest_reach_px,
            hang_time_seconds = EXCLUDED.hang_time_seconds,
            idle_seconds      = EXCLUDED.idle_seconds,
            config_hash       = EXCLUDED.config_hash
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
            bool(a.send),
            a.attempts_count,
            str(a.route_source),
            a.overlay_path,
            a.highlight_path,
            a.dynamic_moves,
            a.longest_reach_px,
            a.hang_time_seconds,
            a.idle_seconds,
            a.config_hash,
        ),
    )
    return cur.fetchone()["id"]


def upsert_route(conn: psycopg.Connection, r: Route) -> int:
    cur = conn.execute(
        """
        INSERT INTO route(wall_id, color, sample_frame_path, hold_layout,
                          layout_embedding, origin, cluster_confidence)
        VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)
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
    return cur.fetchone()["id"]


def leaderboard(conn: psycopg.Connection, route_id: int) -> list[dict[str, Any]]:
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
         WHERE a.route_id = %s
         ORDER BY a.send DESC, a.time_seconds ASC
        """,
        (route_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_routes(conn: psycopg.Connection) -> list[dict[str, Any]]:
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


def _row_to_video(row: dict[str, Any]) -> Video:
    report = row["ingest_report"]
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
        ingest_report=report if isinstance(report, dict) or report is None else json.loads(report),
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
