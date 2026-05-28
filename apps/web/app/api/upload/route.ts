import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve, extname } from "node:path";

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { currentUser } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 600; // long pipelines (pose + render) can take minutes

function repoRoot(): string {
  // apps/web → apps → repo root
  return resolve(process.cwd(), "..", "..");
}

function pythonBin(): string {
  // ARTEMIS_PYTHON is configured relative to apps/web (matching the build
  // workdir). spawn() resolves against the child cwd (repoRoot) so we
  // resolve to an absolute path here first.
  const env = process.env.ARTEMIS_PYTHON;
  if (env) {
    return resolve(process.cwd(), env);
  }
  return resolve(repoRoot(), ".venv/bin/python");
}

interface UploadResult {
  attemptId: number | null;
}

async function runPipeline(args: {
  rawPath: string;
  climber: string;
  color: string | null;
  gym: string;
  title: string | null;
  userId: number;
}): Promise<UploadResult> {
  // Invoke a tiny Python harness that calls orchestrate.process_uploaded_file
  // and prints `ATTEMPT_ID=<n|None>` on its last line. The harness lives in
  // scripts/ so it shares the same package layout as the existing CLI.
  const py = pythonBin();
  const harness = resolve(repoRoot(), "scripts/web_upload_harness.py");
  const payload = JSON.stringify(args);

  return await new Promise<UploadResult>((resolveP, rejectP) => {
    const child = spawn(py, [harness], {
      cwd: repoRoot(),
      env: { ...process.env, PYTHONPATH: resolve(repoRoot(), "src") },
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d: Buffer) => {
      stdout += d.toString();
    });
    child.stderr.on("data", (d: Buffer) => {
      stderr += d.toString();
    });
    child.on("error", (err) => rejectP(err));
    child.on("close", (code) => {
      if (code !== 0) {
        rejectP(new Error(`pipeline exited ${code}: ${stderr.slice(-2000)}`));
        return;
      }
      const m = /ATTEMPT_ID=(\S+)/.exec(stdout);
      if (!m) {
        rejectP(new Error(`pipeline produced no ATTEMPT_ID. stdout: ${stdout.slice(-2000)}`));
        return;
      }
      const raw = m[1];
      const id = raw === "None" ? null : Number(raw);
      resolveP({ attemptId: Number.isFinite(id) ? (id as number) : null });
    });
    child.stdin.end(payload);
  });
}

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
  // Climber name is always the signed-in user's display name. The form ships
  // it for backwards compat but we trust the session over the request body.
  const climber = user.display_name;
  const color = String(form.get("color") ?? "").trim() || null;
  const gym = String(form.get("gym") ?? "").trim();
  const title = String(form.get("title") ?? "").trim() || null;

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "missing file" }, { status: 400 });
  }

  const bytes = Buffer.from(await file.arrayBuffer());
  const sha = createHash("sha256").update(bytes).digest("hex");
  const suffix = (extname(file.name) || ".mp4").toLowerCase();
  const rawDir = resolve(repoRoot(), "data/raw");
  await mkdir(rawDir, { recursive: true });
  const rawPath = resolve(rawDir, `${sha.slice(0, 12)}${suffix}`);
  await writeFile(rawPath, bytes);

  try {
    const result = await runPipeline({
      rawPath,
      climber,
      color,
      gym,
      title,
      userId: user.id,
    });
    return NextResponse.json(result);
  } catch (err) {
    console.error("upload pipeline failed", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "pipeline failed" },
      { status: 500 },
    );
  }
}
