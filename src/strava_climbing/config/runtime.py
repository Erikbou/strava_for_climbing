"""Runtime switches: demo mode, Stage-2 enable/disable, device hints."""

from __future__ import annotations

import os


def is_demo_mode() -> bool:
    """Demo mode opens a frozen DB read-only and disables uploads."""
    return os.environ.get("STRAVA_CLIMBING_MODE") == "demo"


def stage2_enabled() -> bool:
    """Stage 2 modules are lazy-imported only when this is True."""
    return os.environ.get("STRAVA_CLIMBING_DISABLE_STAGE2") not in ("1", "true", "yes")


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
