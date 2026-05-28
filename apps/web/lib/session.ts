import { cookies } from "next/headers";

const COOKIE = "artemis_sid";

/** Read the per-browser session id from cookies; mint a new one if absent.
 *  Used as the anonymous identity for kudos until real auth lands. */
export async function sessionId(): Promise<string> {
  const c = await cookies();
  const existing = c.get(COOKIE)?.value;
  if (existing) return existing;
  // Set a fresh cookie. Note: server components can read but cannot set
  // cookies during render; callers that need a guaranteed sid should hit
  // an API route or call ensureSessionId() from a route handler.
  return existing ?? "";
}

/** Mint and persist a session id from a route handler / server action. */
export async function ensureSessionId(): Promise<string> {
  const c = await cookies();
  const existing = c.get(COOKIE)?.value;
  if (existing) return existing;
  const sid = crypto.randomUUID().replace(/-/g, "");
  c.set(COOKIE, sid, {
    httpOnly: false,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
  });
  return sid;
}
