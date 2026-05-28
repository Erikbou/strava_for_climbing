/** Tiny client for the in-house Python API service.
 *
 *  Both URL + shared key come from env. The key is optional — when the api
 *  has no `ARTEMIS_API_KEY` set, it operates in open mode for local dev.
 */

export function apiBase(): string {
  const u = process.env.ARTEMIS_API_URL;
  if (!u) {
    throw new Error("ARTEMIS_API_URL is not set");
  }
  return u.replace(/\/+$/, "");
}

export function apiHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const key = process.env.ARTEMIS_API_KEY;
  const headers: Record<string, string> = { ...extra };
  if (key) headers["x-artemis-service-key"] = key;
  return headers;
}

export function mediaUrl(path: string): string {
  return `${apiBase()}/media?path=${encodeURIComponent(path)}`;
}
