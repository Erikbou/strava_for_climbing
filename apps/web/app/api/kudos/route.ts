import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { toggleKudos } from "@/lib/queries";
import { ensureSessionId } from "@/lib/session";

export async function POST(req: NextRequest) {
  let attemptId: number;
  try {
    const body = (await req.json()) as { attemptId?: unknown };
    attemptId = Number(body.attemptId);
  } catch {
    return NextResponse.json({ error: "bad json" }, { status: 400 });
  }
  if (!Number.isFinite(attemptId) || attemptId <= 0) {
    return NextResponse.json({ error: "bad attemptId" }, { status: 400 });
  }
  const sid = await ensureSessionId();
  try {
    const count = await toggleKudos(attemptId, sid);
    return NextResponse.json({ count });
  } catch (err) {
    console.error("toggleKudos failed", err);
    return NextResponse.json({ error: "internal" }, { status: 500 });
  }
}
