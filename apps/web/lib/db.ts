import { Pool, type QueryResultRow } from "pg";

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

export async function q<T extends QueryResultRow>(
  text: string,
  params: ReadonlyArray<unknown> = [],
): Promise<T[]> {
  // Schema bootstrap happens once at api service startup (see apps/api/main.py
  // lifespan), not lazily here. If a query fails with undefined_table /
  // undefined_column, it's a real bug or the api hasn't booted — let it
  // propagate so we see it.
  const result = await pool().query<T>(text, params as unknown[]);
  return result.rows;
}

export async function qOne<T extends QueryResultRow>(
  text: string,
  params: ReadonlyArray<unknown> = [],
): Promise<T | null> {
  const rows = await q<T>(text, params);
  return rows[0] ?? null;
}
