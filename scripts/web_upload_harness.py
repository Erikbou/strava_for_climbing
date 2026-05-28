"""Thin stdin-driven wrapper around `orchestrate.process_uploaded_file`.

Called by `apps/web/app/api/upload/route.ts` to run the existing Python
pipeline on a video the web app just persisted. Stays out of the
codebase's public API; lives in `scripts/` next to other one-shot
utilities (e.g. seed_demo.py).

Protocol:
- Read a single JSON blob from stdin: {rawPath, climber, color, gym, title}.
- Run the pipeline.
- Write `ATTEMPT_ID=<n|None>` on the final stdout line.
- Non-zero exit on any unhandled exception.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    raw_path = Path(payload["rawPath"])
    climber = payload.get("climber") or ""
    color = payload.get("color") or None
    gym = payload.get("gym") or ""
    title = payload.get("title") or None

    from strava_climbing import orchestrate

    attempt_id = orchestrate.process_uploaded_file(
        raw_path,
        climber_name=climber,
        color=color,
        gym=gym,
        title=title,
    )
    print(f"ATTEMPT_ID={attempt_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
