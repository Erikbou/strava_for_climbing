import type { NextRequest } from "next/server";

import { mediaUrl } from "@/lib/api";

/** Thin redirect to the api service's /media endpoint. Keeps the web URL
 *  stable for the browser even though the bytes come from the Python
 *  service. Once we move highlights to S3 + presigned URLs, this stays as
 *  the single indirection point — the client doesn't care. */
export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const path = url.searchParams.get("path");
  if (!path) return new Response("missing path", { status: 400 });
  return Response.redirect(mediaUrl(path), 307);
}
