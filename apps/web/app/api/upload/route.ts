import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { apiBase, apiHeaders } from "@/lib/api";
import { currentUser } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 600;

export async function POST(req: NextRequest) {
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "sign-in required" }, { status: 401 });
  }

  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json({ error: "bad form data" }, { status: 400 });
  }
  const file = form.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "missing file" }, { status: 400 });
  }

  // Trust the session for identity; the form's "climber" field, if any, is
  // ignored. Forward the multipart to the api as a fresh FormData so we
  // can attach the user id server-side.
  const forwarded = new FormData();
  forwarded.set("file", file);
  forwarded.set("climber", user.display_name);
  forwarded.set("gym", String(form.get("gym") ?? ""));
  const color = form.get("color");
  if (typeof color === "string" && color.trim()) forwarded.set("color", color);
  const title = form.get("title");
  if (typeof title === "string" && title.trim()) forwarded.set("title", title);
  forwarded.set("user_id", String(user.id));

  try {
    const res = await fetch(`${apiBase()}/process-upload`, {
      method: "POST",
      headers: apiHeaders(),
      body: forwarded,
    });
    const data = (await res.json().catch(() => ({}))) as {
      job_id?: number;
      status?: string;
      detail?: string;
    };
    if (!res.ok) {
      return NextResponse.json(
        { error: data.detail ?? `upload failed (${res.status})` },
        { status: res.status >= 500 ? 500 : 400 },
      );
    }
    return NextResponse.json({ jobId: data.job_id ?? null, status: data.status ?? "queued" });
  } catch (err) {
    console.error("upload forward failed", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "pipeline unreachable" },
      { status: 502 },
    );
  }
}
