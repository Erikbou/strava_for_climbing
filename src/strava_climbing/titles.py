"""Activity-title helpers.

`auto_title(...)` returns the deterministic, Strava-style fallback used when
the climber doesn't pick a name. `random_title()` returns a fun two-word
combo for the "surprise me" button on the upload form.
"""

from __future__ import annotations

import random
from typing import Any

from .config import gym as G

_ADJECTIVES = (
    "Crusty", "Pumpy", "Spicy", "Crispy", "Burly", "Sloppy", "Greasy",
    "Frosty", "Sticky", "Sketchy", "Heady", "Beta-Heavy", "Gritty",
    "Lofty", "Sweaty", "Stoked", "Smooth", "Casual", "Sunset", "Twilight",
    "First-Try", "Last-Light", "Morning", "Sunday",
)

_NOUNS = (
    "Crimper", "Slab Session", "Send Train", "Whip", "Project", "Flash",
    "Burner", "Pull", "Cruise", "Shuffle", "Dyno", "Heel Hook",
    "Sloper Saga", "Mantle", "Top-Out", "Lap", "Lockoff", "Compression",
    "Vibe", "Send",
)


def random_title(seed: int | None = None) -> str:
    rng = random.Random(seed)
    return f"{rng.choice(_ADJECTIVES)} {rng.choice(_NOUNS)}"


def auto_title(row: dict[str, Any]) -> str:
    """Deterministic title derived from the climb metadata.

    ``row`` is a dict-shaped attempt joined with route info — see
    ``apps/streamlit/queries.py``.
    """
    color = row.get("route_color")
    verb = "Sent" if row.get("send") else "Attempted"
    if color:
        grade = G.lookup(color) or {}
        grade_str = grade.get("grade") or "—"
        return f"{verb} {color.title()} · {grade_str}"
    return f"{verb} a climb"


def display_title(row: dict[str, Any]) -> str:
    """Use the stored title if the climber set one, else fall back to auto."""
    stored = row.get("title")
    if stored and stored.strip():
        return stored.strip()
    return auto_title(row)


__all__ = ["auto_title", "display_title", "random_title"]
