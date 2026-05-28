import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { AuthError, createSession, loginUser } from "@/lib/auth";

export async function POST(req: NextRequest) {
  let body: { email?: unknown; password?: unknown };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "bad json" }, { status: 400 });
  }
  try {
    const user = await loginUser(String(body.email ?? ""), String(body.password ?? ""));
    await createSession(user.id);
    return NextResponse.json({ ok: true, user });
  } catch (err) {
    if (err instanceof AuthError) {
      return NextResponse.json({ error: err.message, code: err.code }, { status: 400 });
    }
    console.error("login failed", err);
    return NextResponse.json({ error: "internal" }, { status: 500 });
  }
}
