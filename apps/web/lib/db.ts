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
