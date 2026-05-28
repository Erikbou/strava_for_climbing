import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { AuthError, createSession, registerUser } from "@/lib/auth";

export async function POST(req: NextRequest) {
  let body: { email?: unknown; password?: unknown; displayName?: unknown };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "bad json" }, { status: 400 });
  }
  try {
    const user = await registerUser({
      email: String(body.email ?? ""),
      password: String(body.password ?? ""),
      displayName: String(body.displayName ?? ""),
    });
    await createSession(user.id);
    return NextResponse.json({ ok: true, user });
  } catch (err) {
    if (err instanceof AuthError) {
      const status = err.code === "internal" ? 500 : 400;
      return NextResponse.json({ error: err.message, code: err.code }, { status });
    }
    console.error("register failed", err);
    return NextResponse.json({ error: "internal" }, { status: 500 });
  }
}
