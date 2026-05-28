"""Seed the dev Postgres with demo personas and climbs so the Strava-style
UI has something to render before any real video is processed.

Usage (with `specific dev` running):
    DATABASE_URL=postgres://postgres:postgres@127.0.0.1:3299/main \\
        .venv/bin/python scripts/seed_demo.py

Idempotent: re-running clears existing rows in dependency-safe order and
re-inserts the seed set.
"""

from __future__ import annotations

import os
import random
from datetime import UTC, datetime, timedelta

import psycopg

from strava_climbing.config.gym import DEFAULT_GYM
from strava_climbing.db import connect, init_db

CLIMBERS = [
    "Erik Boustedt",
    "Emil Nobrant",
    "Niklavs Visockis",
    "Leonard Xander",
    "Astrid Lindgren",
    "Olof Sjödin",
]

# Each route = (color, wall_area). Color drives the grade lookup.
ROUTES = [
    ("orange", "Slab Wall"),
    ("blue",   "Overhang Cave"),
    ("green",  "Slab Wall"),
    ("red",    "Vertical Wall"),
    ("purple", "Overhang Cave"),
    ("yellow", "Slab Wall"),
]


def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is not set — start `specific dev` first.")

    init_db()
    rng = random.Random(20260528)
    now = datetime.now(UTC)

    with connect() as conn:
        _wipe(conn)

        climber_ids = [
            conn.execute(
                "INSERT INTO climber(name) VALUES (%s) RETURNING id", (name,)
            ).fetchone()["id"]
            for name in CLIMBERS
        ]

        wall_id = conn.execute(
            "INSERT INTO wall(gym_name) VALUES (%s) RETURNING id", (DEFAULT_GYM,)
        ).fetchone()["id"]

        route_ids: list[int] = []
        for color, _area in ROUTES:
            rid = conn.execute(
                "INSERT INTO route(wall_id, color, origin) VALUES (%s, %s, 'manual') "
                "RETURNING id",
                (wall_id, color),
            ).fetchone()["id"]
            route_ids.append(rid)

        # One synthetic video row so attempt.video_id has a target.
        video_id = conn.execute(
            """
            INSERT INTO video(source_path, normalized_path, source_sha256,
                              duration_seconds, width, height, fps,
                              ingest_status)
            VALUES ('seed://demo.mov', 'seed://demo.mp4', 'seed-sha-demo',
                    60.0, 1280, 720, 30.0, 'ok')
            RETURNING id
            """
        ).fetchone()["id"]

        # ~20 attempts spread across climbers + routes + the last 5 days.
        attempts_to_insert = []
        for i in range(22):
            climber_id = rng.choice(climber_ids)
            route_id = rng.choice(route_ids)
            send = rng.random() < 0.55
            time_seconds = rng.uniform(8.0, 65.0) if send else rng.uniform(4.0, 25.0)
            smoothness_pct = rng.uniform(35.0, 95.0) if send else rng.uniform(10.0, 60.0)
            dynamic_moves = rng.randint(1, 7)
            longest_reach_px = rng.uniform(60.0, 220.0)
            hang_time_seconds = rng.uniform(0.3, 4.5)
            idle_seconds = rng.uniform(0.5, 9.0)
            posted_at = now - timedelta(
                days=rng.randint(0, 5), hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
            )
            start_frame = i * 1000
            end_frame = start_frame + int(time_seconds * 30)
            attempts_to_insert.append(
                (
                    climber_id, route_id, video_id, start_frame, end_frame,
                    time_seconds, smoothness_pct, send, 1, "manual",
                    None, None, dynamic_moves, longest_reach_px,
                    hang_time_seconds, idle_seconds, posted_at, "seed-cfg",
                )
            )

        conn.cursor().executemany(
            """
            INSERT INTO attempt(climber_id, route_id, video_id,
                                start_frame, end_frame, time_seconds,
                                smoothness_pct, send, attempts_count,
                                route_source, overlay_path, highlight_path,
                                dynamic_moves, longest_reach_px,
                                hang_time_seconds, idle_seconds,
                                posted_at, config_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            attempts_to_insert,
        )

    print(
        f"Seeded {len(CLIMBERS)} climbers, {len(ROUTES)} routes, "
        f"{len(attempts_to_insert)} attempts in `{DEFAULT_GYM}`."
    )


def _wipe(conn: psycopg.Connection) -> None:
    conn.execute("TRUNCATE TABLE attempt, hold, route, wall, video, climber RESTART IDENTITY CASCADE")


if __name__ == "__main__":
    main()
