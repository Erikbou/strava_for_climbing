"""Color-to-grade lookup tables, hardcoded per Leonard's product brief.

v1 commits to a single gym so the demo has a deterministic surface. Adding a
second gym is a follow-up.
"""

from __future__ import annotations

DEFAULT_GYM = "Klättercentret Akalla"

# Color names match what shows up in `route.color`. The grade is the V-scale
# label the gym uses for that color band, plus a human-readable difficulty hint.
COLOR_GRADES: dict[str, dict[str, dict[str, str]]] = {
    "Klättercentret Akalla": {
        "white":   {"grade": "V0",    "label": "Beginner"},
        "yellow":  {"grade": "V1",    "label": "Easy"},
        "orange":  {"grade": "V2-V3", "label": "Intermediate"},
        "green":   {"grade": "V3-V4", "label": "Intermediate"},
        "blue":    {"grade": "V4-V5", "label": "Advanced"},
        "red":     {"grade": "V5-V6", "label": "Advanced"},
        "purple":  {"grade": "V6-V7", "label": "Hard"},
        "black":   {"grade": "V7-V8", "label": "Hard"},
        "pink":    {"grade": "V8+",   "label": "Elite"},
    },
}


def lookup(color: str | None, *, gym: str = DEFAULT_GYM) -> dict[str, str] | None:
    """Return `{"grade": ..., "label": ...}` for a color, or None when unknown."""
    if not color:
        return None
    table = COLOR_GRADES.get(gym)
    if not table:
        return None
    return table.get(color.lower())


__all__ = ["COLOR_GRADES", "DEFAULT_GYM", "lookup"]
