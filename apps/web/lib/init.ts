import { spawn } from "node:child_process";
import { resolve } from "node:path";

declare global {
  // eslint-disable-next-line no-var
  var __ARTEMIS_SCHEMA_INIT__: Promise<void> | undefined;
}

function repoRoot(): string {
  // The web app runs from `apps/web/`; the repo root is two levels up.
  return resolve(process.cwd(), "..", "..");
}

function pythonBin(): string {
  // ARTEMIS_PYTHON is configured in specific.hcl relative to apps/web (so it
  // matches the build's workdir). spawn() resolves paths against the child's
  // cwd, which we set to repoRoot — so we must always hand it an absolute
  // path or it'll look in the wrong place.
  const env = process.env.ARTEMIS_PYTHON;
  if (env) {
    return resolve(process.cwd(), env);
  }
  return resolve(repoRoot(), ".venv/bin/python");
}

function runInit(): Promise<void> {
  return new Promise((resolveP, rejectP) => {
    const py = pythonBin();
    const harness = resolve(repoRoot(), "scripts/web_init_schema.py");
    const child = spawn(py, [harness], {
      cwd: repoRoot(),
      env: { ...process.env, PYTHONPATH: resolve(repoRoot(), "src") },
      stdio: ["ignore", "pipe", "pipe"],
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
      if (code === 0 && stdout.includes("INIT_OK")) {
        resolveP();
      } else {
        rejectP(
          new Error(
            `schema init exited ${code}: ${stderr.slice(-1500) || stdout.slice(-1500)}`,
          ),
        );
      }
    });
  });
}

/** Idempotent per-process schema bootstrap. Mirrors the lazy-once pattern in
 *  `apps/streamlit/queries.py` so the web app can run standalone without
 *  requiring the dashboard to have been hit first. */
export function ensureSchema(): Promise<void> {
  if (!globalThis.__ARTEMIS_SCHEMA_INIT__) {
    globalThis.__ARTEMIS_SCHEMA_INIT__ = runInit().catch((err) => {
      // Drop the cached promise on failure so the next request retries.
      globalThis.__ARTEMIS_SCHEMA_INIT__ = undefined;
      throw err;
    });
  }
  return globalThis.__ARTEMIS_SCHEMA_INIT__;
}
