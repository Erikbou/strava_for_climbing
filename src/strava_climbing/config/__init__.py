"""Configuration package. Importing it loads the project ``.env`` once so
downstream modules (db backend selector, Supabase credentials, runtime
toggles) all see the same view of the environment.
"""

from __future__ import annotations

import os
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_DOTENV_CANDIDATES = (
    _PACKAGE_ROOT / ".env",
    Path.cwd() / ".env",
)


def _load_dotenv_once() -> None:
    """Minimal ``.env`` loader — full python-dotenv is overkill for a handful of keys.

    Values already present in ``os.environ`` win, matching ``python-dotenv``'s
    ``override=False`` default. Quotes around values are stripped.
    """
    for path in _DOTENV_CANDIDATES:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv_once()
