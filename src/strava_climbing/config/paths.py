"""Filesystem layout. Everything is relative to ``DATA_ROOT``.

Override with the ``STRAVA_CLIMBING_DATA_ROOT`` env var so the demo can run
out of a different folder. The structured database lives in Supabase, not on
disk — only derived media (normalized videos, pose caches, overlay clips,
sample frames) is kept locally.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = Path(os.environ.get("STRAVA_CLIMBING_DATA_ROOT", REPO_ROOT / "data"))

RAW_DIR = DATA_ROOT / "raw"
NORMALIZED_DIR = DATA_ROOT / "normalized"
OVERLAYS_DIR = DATA_ROOT / "overlays"
CACHE_DIR = DATA_ROOT / "cache"
MANIFESTS_DIR = DATA_ROOT / "manifests"
POSE_CACHE_DIR = CACHE_DIR / "pose"

INGEST_REPORT_PATH = DATA_ROOT / "ingest_report.json"

MODELS_DIR = REPO_ROOT / "models"


def ensure_dirs() -> None:
    for d in (
        DATA_ROOT,
        RAW_DIR,
        NORMALIZED_DIR,
        OVERLAYS_DIR,
        CACHE_DIR,
        MANIFESTS_DIR,
        POSE_CACHE_DIR,
        MODELS_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)
