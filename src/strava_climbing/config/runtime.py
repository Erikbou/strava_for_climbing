"""Runtime switches: backend selection, demo mode, Stage-2 toggle, device hints."""

from __future__ import annotations

import os


def is_demo_mode() -> bool:
    """Demo mode treats the configured backend as read-only and disables uploads."""
    return os.environ.get("STRAVA_CLIMBING_MODE") == "demo"


def stage2_enabled() -> bool:
    """Stage 2 modules are lazy-imported only when this is True."""
    return os.environ.get("STRAVA_CLIMBING_DISABLE_STAGE2") not in ("1", "true", "yes")


def use_supabase() -> bool:
    """Pick the persistence backend.

    Explicit override: set ``STRAVA_CLIMBING_BACKEND=supabase`` or ``=sqlite``.
    Auto: if a Supabase URL is configured, use Supabase; otherwise fall back to
    the local SQLite + filesystem implementation so the project runs offline.
    """
    explicit = os.environ.get("STRAVA_CLIMBING_BACKEND", "").strip().lower()
    if explicit == "supabase":
        return True
    if explicit == "sqlite":
        return False
    return bool(
        os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
        or os.environ.get("SUPABASE_URL")
    )


def preferred_device() -> str:
    """Best-effort device hint for torch/ultralytics. ``cuda`` > ``mps`` > ``cpu``."""
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"
