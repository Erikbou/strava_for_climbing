/** Map a server-side highlight/overlay path stored in Postgres to a URL the
 *  browser can fetch. The Python pipeline writes files into `data/highlights`
 *  and `data/overlays` (relative to repo root). We expose those over an API
 *  route at /api/media that streams the file with byte-range support. */
export function videoSrcFor(p: string | null | undefined): string | null {
  if (!p) return null;
  return `/api/media?path=${encodeURIComponent(p)}`;
}
