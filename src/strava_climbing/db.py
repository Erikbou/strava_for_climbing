"""Persistence façade.

Re-exports the active backend so callers can stay backend-agnostic:

    from strava_climbing import db
    db.init_db()
    db.upsert_attempt(...)
    db.overlay_playback_source(key)  # URL in Supabase mode, Path locally

Backend choice is made by ``config.runtime.use_supabase()``:

- ``STRAVA_CLIMBING_BACKEND=supabase`` → forces Supabase
- ``STRAVA_CLIMBING_BACKEND=sqlite``   → forces SQLite + local files
- otherwise: Supabase if ``NEXT_PUBLIC_SUPABASE_URL`` (or ``SUPABASE_URL``)
  is set, else SQLite.

The two backends expose the same names; this module is the single
import point so swapping is a one-env-var flip.
"""

from __future__ import annotations

from .config import runtime as R

if R.use_supabase():
    from ._backend_supabase import *  # noqa: F401,F403
    from ._backend_supabase import __all__ as __all__  # noqa: PLE0604
else:
    from ._backend_sqlite import *  # noqa: F401,F403
    from ._backend_sqlite import __all__ as __all__  # noqa: PLE0604
