import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { apiBase, apiHeaders } from "@/lib/api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Thin proxy to api /jobs/:id. The UI polls this every couple seconds while
 *  an upload is processing. Auth check is intentionally omitted — job ids
 *  are integers and the worst leak is "this id is processing"; once we have
 *  per-user ACLs we'll filter here. */
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const jobId = Number(id);
  if (!Number.isFinite(jobId) || jobId <= 0) {
    return NextResponse.json({ error: "bad id" }, { status: 400 });
  }
  try {
    const res = await fetch(`${apiBase()}/jobs/${jobId}`, {
      method: "GET",
      headers: apiHeaders(),
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return NextResponse.json(data, { status: res.status });
    }
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "api unreachable" },
      { status: 502 },
    );
  }
}
