import { Pool, type QueryResultRow } from "pg";

import { ensureSchema } from "./init";

declare global {
  // eslint-disable-next-line no-var
  var __ARTEMIS_PG_POOL__: Pool | undefined;
}

function makePool(): Pool {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error("DATABASE_URL is not set");
  }
  return new Pool({
    connectionString,
    max: 8,
    idleTimeoutMillis: 30_000,
  });
}

export function pool(): Pool {
  if (!globalThis.__ARTEMIS_PG_POOL__) {
    globalThis.__ARTEMIS_PG_POOL__ = makePool();
  }
  return globalThis.__ARTEMIS_PG_POOL__;
}

async function runQuery<T extends QueryResultRow>(
  text: string,
  params: ReadonlyArray<unknown>,
): Promise<T[]> {
  const result = await pool().query<T>(text, params as unknown[]);
  return result.rows;
}

export async function q<T extends QueryResultRow>(
  text: string,
  params: ReadonlyArray<unknown> = [],
): Promise<T[]> {
  try {
    await ensureSchema();
    return await runQuery<T>(text, params);
  } catch (err) {
    // Mirror queries.py's _retry_after_migrate: if the schema is stale (table
    // or column missing), re-run init_db and try once more.
    if (isMissingRelation(err)) {
      await ensureSchema();
      return await runQuery<T>(text, params);
    }
    throw err;
  }
}

export async function qOne<T extends QueryResultRow>(
  text: string,
  params: ReadonlyArray<unknown> = [],
): Promise<T | null> {
  const rows = await q<T>(text, params);
  return rows[0] ?? null;
}

function isMissingRelation(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const code = (err as { code?: unknown }).code;
  // 42P01 = undefined_table, 42703 = undefined_column
  return code === "42P01" || code === "42703";
}
