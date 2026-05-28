import { createReadStream, statSync } from "node:fs";
import { resolve, sep } from "node:path";

import type { NextRequest } from "next/server";

/** Serve highlight / overlay videos stored on disk by the Python pipeline.
 *  Resolves the requested path against a configured media root and refuses
 *  to serve anything outside it. Supports HTTP byte-range so <video> can
 *  seek without downloading the whole file. */

function mediaRoots(): string[] {
  const roots: string[] = [];
  const explicit = process.env.ARTEMIS_MEDIA_ROOT;
  if (explicit) {
    // Allow comma-separated list of paths, each resolved against apps/web's cwd.
    for (const p of explicit.split(",")) {
      const trimmed = p.trim();
      if (trimmed) roots.push(resolve(process.cwd(), trimmed));
    }
  } else {
    // Default: repo root's data/ directory + this app's own data/.
    roots.push(resolve(process.cwd(), "..", "..", "data"));
    roots.push(resolve(process.cwd(), "data"));
  }
  return roots;
}

function safeResolve(requested: string): string | null {
  const candidate = resolve(requested);
  for (const root of mediaRoots()) {
    const withSep = root.endsWith(sep) ? root : root + sep;
    if (candidate === root || candidate.startsWith(withSep)) {
      try {
        const s = statSync(candidate);
        if (!s.isFile()) return null;
        return candidate;
      } catch {
        return null;
      }
    }
  }
  return null;
}

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const raw = url.searchParams.get("path");
  if (!raw) return new Response("missing path", { status: 400 });
  const file = safeResolve(raw);
  if (!file) return new Response("not found", { status: 404 });

  const stat = statSync(file);
  const total = stat.size;
  const range = req.headers.get("range");
  const headers: Record<string, string> = {
    "content-type": "video/mp4",
    "accept-ranges": "bytes",
    "cache-control": "private, max-age=60",
  };

  if (range) {
    const m = /bytes=(\d+)-(\d+)?/.exec(range);
    if (!m) return new Response("bad range", { status: 416 });
    const start = Number(m[1]);
    const end = m[2] ? Math.min(Number(m[2]), total - 1) : total - 1;
    const chunkSize = end - start + 1;
    headers["content-range"] = `bytes ${start}-${end}/${total}`;
    headers["content-length"] = String(chunkSize);
    const stream = createReadStream(file, { start, end });
    return new Response(stream as unknown as ReadableStream, {
      status: 206,
      headers,
    });
  }

  headers["content-length"] = String(total);
  const stream = createReadStream(file);
  return new Response(stream as unknown as ReadableStream, {
    status: 200,
    headers,
  });
}
