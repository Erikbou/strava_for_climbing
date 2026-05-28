import { apiBase, apiHeaders } from "./api";

declare global {
  // eslint-disable-next-line no-var
  var __ARTEMIS_SCHEMA_INIT__: Promise<void> | undefined;
}

async function runInit(): Promise<void> {
  const res = await fetch(`${apiBase()}/schema/init`, {
    method: "POST",
    headers: apiHeaders(),
    body: "",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`schema init failed (${res.status}): ${text.slice(-500)}`);
  }
}

/** Idempotent per-process schema bootstrap. The Python api owns the SQL;
 *  this kicks it once and caches the resolved promise on globalThis so
 *  concurrent first-page-loads don't fan out into N init requests. */
export function ensureSchema(): Promise<void> {
  if (!globalThis.__ARTEMIS_SCHEMA_INIT__) {
    globalThis.__ARTEMIS_SCHEMA_INIT__ = runInit().catch((err) => {
      globalThis.__ARTEMIS_SCHEMA_INIT__ = undefined;
      throw err;
    });
  }
  return globalThis.__ARTEMIS_SCHEMA_INIT__;
}
