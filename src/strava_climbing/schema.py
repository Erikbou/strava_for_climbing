from dataclasses import dataclass, field
from datetime import datetime

from .provenance import RouteSource


@dataclass(slots=True, frozen=True)
class Climber:
    id: int | None
    name: str
    aliases: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class Video:
    id: int | None
    source_path: str
    normalized_path: str
    source_sha256: str
    duration_seconds: float
    width: int
    height: int
    fps: float
    ingest_status: str  # "pending" | "ok" | "rejected" | "error"
    ingest_report: dict | None = None


@dataclass(slots=True, frozen=True)
class Wall:
    id: int | None
    gym_name: str
    sample_frame_path: str | None = None
    dinov3_embedding: bytes | None = None


@dataclass(slots=True, frozen=True)
class Route:
    id: int | None
    wall_id: int
    origin: RouteSource
    color: str | None = None
    sample_frame_path: str | None = None
    hold_layout: dict | None = None
    layout_embedding: bytes | None = None
    cluster_confidence: float | None = None


@dataclass(slots=True, frozen=True)
class Hold:
    id: int | None
    wall_id: int
    x: float
    y: float
    w: float
    h: float
    route_id: int | None = None
    color_hsv: dict | None = None


@dataclass(slots=True, frozen=True)
class Attempt:
    id: int | None
    video_id: int
    start_frame: int
    end_frame: int
    time_seconds: float
    send: bool
    attempts_count: int
    route_source: RouteSource
    config_hash: str
    climber_id: int | None = None
    route_id: int | None = None
    smoothness_raw: float | None = None
    smoothness_pct: float | None = None
    overlay_path: str | None = None
    highlight_path: str | None = None
    dynamic_moves: int | None = None
    longest_reach_px: float | None = None
    hang_time_seconds: float | None = None
    idle_seconds: float | None = None
    title: str | None = None


@dataclass(slots=True, frozen=True)
class IngestReportEntry:
    """One row in data/ingest_report.json."""

    source_path: str
    status: str
    timestamp: datetime
    normalized_path: str | None = None
    source_sha256: str | None = None
    reason: str | None = None
    metadata: dict | None = None
