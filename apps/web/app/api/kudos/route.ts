import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { currentUser } from "@/lib/auth";
import { toggleKudos } from "@/lib/queries";

export async function POST(req: NextRequest) {
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "sign-in required" }, { status: 401 });
  }
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
  try {
    const count = await toggleKudos(attemptId, user.id);
    return NextResponse.json({ count });
  } catch (err) {
    console.error("toggleKudos failed", err);
    return NextResponse.json({ error: "internal" }, { status: 500 });
  }
}
