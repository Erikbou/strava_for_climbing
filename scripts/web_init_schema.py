"""Run the same idempotent schema migration the Streamlit dashboard does.

Called by `apps/web/lib/init.ts` once per Node process so the Next.js app
doesn't depend on the dashboard being hit first to bootstrap the DB. Reads
DATABASE_URL from the environment via `strava_climbing.db.connect`.
"""

from __future__ import annotations

import sys


def main() -> int:
    from strava_climbing.db import init_db

    init_db()
    print("INIT_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
