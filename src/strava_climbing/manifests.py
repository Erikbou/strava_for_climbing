"""Per-(video, stage) manifests for idempotent re-runs.

Lightweight — a JSON file per ``manifests/{video_id}/{stage}.json``. Re-running
a stage with the same ``inputs_hash`` short-circuits to ``skipped`` instead of
re-doing the work.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from .config import paths as P

StageName = Literal["pose", "boundaries", "metrics", "overlay"]
Status = Literal["ok", "skipped", "error"]


@dataclass(slots=True, frozen=True)
class Manifest:
    stage: str
    video_id: int
    status: Status
    inputs_hash: str
    started_at: str
    finished_at: str
    error: str | None = None
    outputs: list[str] | None = None


def _path(video_id: int, stage: str) -> Path:
    return P.MANIFESTS_DIR / str(video_id) / f"{stage}.json"


def read(video_id: int, stage: str) -> Manifest | None:
    p = _path(video_id, stage)
    if not p.exists():
        return None
    raw = json.loads(p.read_text())
    return Manifest(**raw)


def write(m: Manifest) -> None:
    p = _path(m.video_id, m.stage)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(m), indent=2))


def is_complete(video_id: int, stage: str, inputs_hash: str) -> bool:
    m = read(video_id, stage)
    return m is not None and m.status == "ok" and m.inputs_hash == inputs_hash


def stamp() -> str:
    return datetime.now(UTC).isoformat()


__all__ = ["Manifest", "is_complete", "read", "stamp", "write"]
