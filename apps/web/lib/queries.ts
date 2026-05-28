import { q, qOne } from "./db";

export interface FeedRow {
  attempt_id: number;
  title: string | null;
  time_seconds: number | null;
  smoothness_pct: number | null;
  dynamic_moves: number | null;
  longest_reach_px: number | null;
  hang_time_seconds: number | null;
  idle_seconds: number | null;
  send: boolean;
  overlay_path: string | null;
  highlight_path: string | null;
  posted_at: Date | null;
  climber_id: number | null;
  climber_name: string | null;
  route_id: number | null;
  route_color: string | null;
  gym_name: string | null;
}

export interface AttemptDetailRow extends FeedRow {
  normalized_path: string | null;
}

export interface ClimberRow {
  id: number;
  name: string;
  attempts_logged: number;
  sends: number;
  fastest_send_seconds: number | null;
}

export interface ClimberListRow extends ClimberRow {
  last_seen: Date | null;
}

export interface ClimberAttemptRow {
  attempt_id: number;
  time_seconds: number | null;
  send: boolean;
  posted_at: Date | null;
  route_color: string | null;
  gym_name: string | null;
}

export async function feed(limit = 50): Promise<FeedRow[]> {
  return q<FeedRow>(
    `SELECT a.id            AS attempt_id,
            a.title         AS title,
            a.time_seconds  AS time_seconds,
            a.smoothness_pct AS smoothness_pct,
            a.dynamic_moves AS dynamic_moves,
            a.longest_reach_px AS longest_reach_px,
            a.hang_time_seconds AS hang_time_seconds,
            a.idle_seconds  AS idle_seconds,
            a.send          AS send,
            a.overlay_path  AS overlay_path,
            a.highlight_path AS highlight_path,
            a.posted_at     AS posted_at,
            c.id            AS climber_id,
            c.name          AS climber_name,
            r.id            AS route_id,
            r.color         AS route_color,
            w.gym_name      AS gym_name
       FROM attempt a
       LEFT JOIN climber c ON c.id = a.climber_id
       LEFT JOIN route   r ON r.id = a.route_id
       LEFT JOIN wall    w ON w.id = r.wall_id
      ORDER BY a.posted_at DESC, a.id DESC
      LIMIT $1`,
    [limit],
  );
}

export async function attempt(attemptId: number): Promise<AttemptDetailRow | null> {
  return qOne<AttemptDetailRow>(
    `SELECT a.id            AS attempt_id,
            a.title         AS title,
            a.time_seconds  AS time_seconds,
            a.smoothness_pct AS smoothness_pct,
            a.dynamic_moves AS dynamic_moves,
            a.longest_reach_px AS longest_reach_px,
            a.hang_time_seconds AS hang_time_seconds,
            a.idle_seconds  AS idle_seconds,
            a.send          AS send,
            a.overlay_path  AS overlay_path,
            a.highlight_path AS highlight_path,
            a.posted_at     AS posted_at,
            c.id            AS climber_id,
            c.name          AS climber_name,
            r.id            AS route_id,
            r.color         AS route_color,
            w.gym_name      AS gym_name,
            v.normalized_path AS normalized_path
       FROM attempt a
       LEFT JOIN climber c ON c.id = a.climber_id
       LEFT JOIN route   r ON r.id = a.route_id
       LEFT JOIN wall    w ON w.id = r.wall_id
       LEFT JOIN video   v ON v.id = a.video_id
      WHERE a.id = $1`,
    [attemptId],
  );
}

export async function climber(climberId: number): Promise<ClimberRow | null> {
  return qOne<ClimberRow>(
    `SELECT c.id, c.name,
            COUNT(a.id)::int                                   AS attempts_logged,
            (COUNT(*) FILTER (WHERE a.send IS TRUE))::int      AS sends,
            MIN(a.time_seconds) FILTER (WHERE a.send IS TRUE)  AS fastest_send_seconds
       FROM climber c
       LEFT JOIN attempt a ON a.climber_id = c.id
      WHERE c.id = $1
      GROUP BY c.id, c.name`,
    [climberId],
  );
}

export async function climbers(limit = 50): Promise<ClimberListRow[]> {
  return q<ClimberListRow>(
    `SELECT c.id, c.name,
            COUNT(a.id)::int                                   AS attempts_logged,
            (COUNT(*) FILTER (WHERE a.send IS TRUE))::int      AS sends,
            MIN(a.time_seconds) FILTER (WHERE a.send IS TRUE)  AS fastest_send_seconds,
            MAX(a.posted_at)                                    AS last_seen
       FROM climber c
       LEFT JOIN attempt a ON a.climber_id = c.id
      GROUP BY c.id, c.name
      ORDER BY sends DESC NULLS LAST, attempts_logged DESC NULLS LAST,
               c.name ASC
      LIMIT $1`,
    [limit],
  );
}

export async function climberAttempts(
  climberId: number,
  limit = 20,
): Promise<ClimberAttemptRow[]> {
  return q<ClimberAttemptRow>(
    `SELECT a.id            AS attempt_id,
            a.time_seconds  AS time_seconds,
            a.send          AS send,
            a.posted_at     AS posted_at,
            r.color         AS route_color,
            w.gym_name      AS gym_name
       FROM attempt a
       LEFT JOIN route r ON r.id = a.route_id
       LEFT JOIN wall  w ON w.id = r.wall_id
      WHERE a.climber_id = $1
      ORDER BY a.posted_at DESC, a.id DESC
      LIMIT $2`,
    [climberId, limit],
  );
}

export async function kudosCounts(
  attemptIds: ReadonlyArray<number>,
): Promise<Record<number, number>> {
  if (attemptIds.length === 0) return {};
  const rows = await q<{ attempt_id: number; n: string }>(
    `SELECT attempt_id, COUNT(*) AS n
       FROM kudos
      WHERE attempt_id = ANY($1::int[])
      GROUP BY attempt_id`,
    [attemptIds],
  );
  const counts: Record<number, number> = {};
  for (const id of attemptIds) counts[id] = 0;
  for (const r of rows) counts[r.attempt_id] = Number(r.n);
  return counts;
}

export async function myKudos(
  attemptIds: ReadonlyArray<number>,
  userId: number | null,
): Promise<Set<number>> {
  if (attemptIds.length === 0 || !userId) return new Set();
  const rows = await q<{ attempt_id: number }>(
    `SELECT attempt_id FROM kudos
      WHERE user_id = $1 AND attempt_id = ANY($2::int[])`,
    [userId, attemptIds],
  );
  return new Set(rows.map((r) => r.attempt_id));
}

export async function toggleKudos(
  attemptId: number,
  userId: number,
): Promise<number> {
  const existing = await qOne<{ ok: number }>(
    `SELECT 1 AS ok FROM kudos WHERE attempt_id = $1 AND user_id = $2`,
    [attemptId, userId],
  );
  if (existing) {
    await q(
      `DELETE FROM kudos WHERE attempt_id = $1 AND user_id = $2`,
      [attemptId, userId],
    );
  } else {
    await q(
      `INSERT INTO kudos(attempt_id, user_id) VALUES ($1, $2)
       ON CONFLICT DO NOTHING`,
      [attemptId, userId],
    );
  }
  const row = await qOne<{ n: string }>(
    `SELECT COUNT(*) AS n FROM kudos WHERE attempt_id = $1`,
    [attemptId],
  );
  return Number(row?.n ?? 0);
}

/** Resolve "me" → the current user's climber id (auto-created on register).
 *  Falls back to creating the climber row if it's missing (e.g. user signed
 *  up before the auto-create hook landed). */
export async function climberIdForUser(
  userId: number,
  displayName: string,
): Promise<number | null> {
  const row = await qOne<{ id: number }>(
    `SELECT id FROM climber WHERE user_id = $1`,
    [userId],
  );
  if (row) return row.id;
  const inserted = await qOne<{ id: number }>(
    `INSERT INTO climber(name, user_id) VALUES ($1, $2)
     ON CONFLICT (LOWER(name)) DO UPDATE
       SET user_id = COALESCE(climber.user_id, EXCLUDED.user_id)
     RETURNING id`,
    [displayName, userId],
  );
  return inserted?.id ?? null;
}
