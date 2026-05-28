"""Thin stdin-driven wrapper around `orchestrate.process_uploaded_file`.

Called by `apps/web/app/api/upload/route.ts` to run the existing Python
pipeline on a video the web app just persisted. Stays out of the
codebase's public API; lives in `scripts/` next to other one-shot
utilities (e.g. seed_demo.py).

Protocol:
- Read a single JSON blob from stdin:
    {rawPath, climber, color, gym, title, userId}
- Run the pipeline.
- Backfill climber.user_id + attempt.user_id from `userId` so the new
  attempt is owned by the signed-in user (the orchestrate path itself
  doesn't know about auth yet).
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
    user_id = payload.get("userId")

    from strava_climbing import orchestrate
    from strava_climbing.db import connect

    attempt_id = orchestrate.process_uploaded_file(
        raw_path,
        climber_name=climber,
        color=color,
        gym=gym,
        title=title,
    )

    # Link the new attempt + climber back to the signed-in user. Best-effort:
    # if the columns or user row are missing for some reason, we still want
    # the attempt itself to be visible — the auth join in queries.ts uses
    # LEFT JOIN so a NULL user_id won't hide the row.
    if attempt_id is not None and isinstance(user_id, int):
        try:
            with connect() as conn:
                conn.execute(
                    "UPDATE attempt SET user_id = %s WHERE id = %s",
                    (user_id, attempt_id),
                )
                conn.execute(
                    """
                    UPDATE climber SET user_id = %s
                     WHERE id = (SELECT climber_id FROM attempt WHERE id = %s)
                       AND user_id IS NULL
                    """,
                    (user_id, attempt_id),
                )
        except Exception as exc:  # noqa: BLE001 — never fail the upload over this.
            print(f"WARN_LINK_USER={exc}", file=sys.stderr)

    print(f"ATTEMPT_ID={attempt_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
