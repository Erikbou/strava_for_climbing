"""ffmpeg + ffprobe normalization layer.

Implements the verified 2026 incantation from the deepened plan (Addendum §D):
- ``-fps_mode cfr`` (replaces deprecated ``-vsync cfr``)
- 720p long-edge downsample at ingest (~4-5× speed-up on downstream pose)
- ``setpts=N/FRAME_RATE/TB`` filter to fix VFR timestamp gaps
- HDR10 tone-mapping branch (zscale → tonemap=hable → zscale)
- Audio dropped by default (CV pipeline doesn't use it)
- Source-file SHA-256 is the dedup key, never the normalized output
  (``libx264 -preset medium`` is not bit-exact across runs)
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from . import storage
from .config import paths as P
from .config import runtime as R
from .config import thresholds as T
from .db import connect, get_video_by_sha, upsert_video
from .schema import IngestReportEntry, Video

log = logging.getLogger("strava_climbing.ingest")

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}
_CHUNK = 1 << 20  # 1 MiB


def sha256_file(path: Path) -> str:
    """Stream the file through SHA-256. Avoids loading large videos into RAM."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_video(path: Path) -> dict:
    """Run ffprobe and parse the JSON. See Addendum §D for field semantics."""
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        text=True,
    )
    d = json.loads(out)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    if v is None:
        raise ValueError(f"no video stream in {path}")

    rotation = 0
    for sd in v.get("side_data_list", []):
        if sd.get("side_data_type") == "Display Matrix":
            rotation = sd.get("rotation", 0)

    return {
        "duration_seconds": float(d["format"].get("duration", 0.0)),
        "width": int(v["width"]),
        "height": int(v["height"]),
        "codec": v.get("codec_name", ""),
        "fps_real": _eval_rate(v.get("r_frame_rate", "30/1")),
        "fps_avg": _eval_rate(v.get("avg_frame_rate", "30/1")),
        "rotation_degrees": rotation,
        "is_hdr": "bt2020" in v.get("color_space", "") or "10le" in v.get("pix_fmt", ""),
        "is_vfr": v.get("r_frame_rate") != v.get("avg_frame_rate"),
        "creation_time": d.get("format", {}).get("tags", {}).get("creation_time"),
    }


def _eval_rate(rate: str) -> float:
    """Parse ffmpeg rational like '30/1' or '30000/1001'."""
    if "/" in rate:
        num, den = rate.split("/", 1)
        try:
            return float(num) / float(den) if float(den) else 0.0
        except ValueError:
            return 0.0
    try:
        return float(rate)
    except ValueError:
        return 0.0


def normalize_video(
    src: Path,
    dst: Path,
    *,
    fps: int = T.TARGET_FPS,
    max_long_edge: int = T.TARGET_MAX_LONG_EDGE,
    is_hdr: bool = False,
    crf: int = 23,
    use_videotoolbox: bool = False,
) -> None:
    """Run ffmpeg with the verified flag set. Caller decides ``is_hdr`` from probe."""
    dst.parent.mkdir(parents=True, exist_ok=True)

    scale_filter = (
        f"scale='min({max_long_edge},iw)':'min({int(max_long_edge * 9 / 16)},ih)'"
        ":force_original_aspect_ratio=decrease"
    )
    pad_filter = "pad=ceil(iw/2)*2:ceil(ih/2)*2"
    fmt_filter = "format=yuv420p"
    pts_filter = "setpts=N/FRAME_RATE/TB"

    hdr_filter = ""
    if is_hdr:
        hdr_filter = (
            "zscale=matrix=bt709:transfer=bt709:primaries=bt709:m=i:npl=1000,"
            "tonemap=tonemap=hable:desat=0:peak=400,"
            "zscale=matrix=bt709:transfer=bt709:primaries=bt709,"
        )

    vf = f"{scale_filter},{pad_filter},{hdr_filter}{fmt_filter},{pts_filter}"

    cmd: list[str] = ["ffmpeg", "-y"]
    if use_videotoolbox:
        cmd += ["-hwaccel", "videotoolbox"]
    cmd += [
        "-i",
        str(src),
        "-fps_mode",
        "cfr",
        "-r",
        str(fps),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "medium",
        "-crf",
        str(crf),
        "-movflags",
        "+faststart",
        "-an",
        str(dst),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _detect_videotoolbox() -> bool:
    """videotoolbox is the 20× HEVC decode win on Apple Silicon."""
    try:
        out = subprocess.check_output(["ffmpeg", "-hide_banner", "-hwaccels"], text=True)
        return "videotoolbox" in out
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _write_report(entries: list[IngestReportEntry]) -> None:
    payload = [
        {
            **asdict(e),
            "timestamp": e.timestamp.isoformat(),
        }
        for e in entries
    ]
    P.INGEST_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    P.INGEST_REPORT_PATH.write_text(json.dumps(payload, indent=2))


def ingest_directory(raw_dir: Path | None = None) -> dict:
    """Top-level orchestration. Idempotent on source-file SHA-256."""
    raw = raw_dir or P.RAW_DIR
    P.ensure_dirs()

    client = connect()

    use_vt = _detect_videotoolbox()
    entries: list[IngestReportEntry] = []
    stats = {"seen": 0, "ok": 0, "skipped": 0, "rejected": 0, "errored": 0}

    for src in sorted(raw.iterdir()):
        if not src.is_file() or src.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        stats["seen"] += 1
        entry = _ingest_one(client, src, use_vt)
        entries.append(entry)
        stats[_status_bucket(entry.status)] += 1

    _write_report(entries)
    return stats


def _status_bucket(status: str) -> str:
    return {
        "ok": "ok",
        "skipped": "skipped",
        "rejected": "rejected",
        "error": "errored",
    }.get(status, "errored")


def _ingest_one(client, src: Path, use_videotoolbox: bool) -> IngestReportEntry:
    now = datetime.now(UTC)
    try:
        sha = sha256_file(src)
    except OSError as e:
        return IngestReportEntry(
            source_path=str(src),
            status="error",
            timestamp=now,
            reason=f"sha256 failed: {e}",
        )

    existing = get_video_by_sha(client, sha)
    if existing is not None and existing.ingest_status == "ok":
        return IngestReportEntry(
            source_path=str(src),
            status="skipped",
            timestamp=now,
            source_sha256=sha,
            reason=f"already ingested as video.id={existing.id}",
        )

    try:
        meta = probe_video(src)
    except (subprocess.CalledProcessError, ValueError) as e:
        return IngestReportEntry(
            source_path=str(src), status="error", timestamp=now,
            source_sha256=sha, reason=f"ffprobe failed: {e}",
        )

    if meta["duration_seconds"] < T.MIN_VIDEO_DURATION_S:
        return IngestReportEntry(
            source_path=str(src), status="rejected", timestamp=now,
            source_sha256=sha, reason=f"too short ({meta['duration_seconds']:.1f}s)",
            metadata=meta,
        )

    dst = P.NORMALIZED_DIR / f"{sha[:12]}.mp4"
    try:
        normalize_video(src, dst, is_hdr=meta["is_hdr"], use_videotoolbox=use_videotoolbox)
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b"").decode("utf-8", errors="replace")[:300]
        return IngestReportEntry(
            source_path=str(src), status="error", timestamp=now,
            source_sha256=sha, reason=f"ffmpeg failed: {stderr}",
            metadata=meta,
        )

    norm_meta = probe_video(dst)

    normalized_bucket_key, upload_error = _publish_normalized(dst, sha)
    report: dict = {"source": meta, "normalized": norm_meta}
    if normalized_bucket_key:
        report["normalized_bucket_key"] = normalized_bucket_key
    if upload_error:
        report["normalized_upload_error"] = upload_error

    upsert_video(
        client,
        Video(
            id=None,
            source_path=str(src),
            normalized_path=str(dst),
            source_sha256=sha,
            duration_seconds=norm_meta["duration_seconds"],
            width=norm_meta["width"],
            height=norm_meta["height"],
            fps=norm_meta["fps_avg"] or T.TARGET_FPS,
            ingest_status="ok",
            ingest_report=report,
            normalized_bucket_key=normalized_bucket_key,
        ),
    )

    return IngestReportEntry(
        source_path=str(src),
        status="ok",
        timestamp=now,
        normalized_path=str(dst),
        source_sha256=sha,
        metadata=norm_meta,
    )


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _publish_normalized(dst: Path, sha: str) -> tuple[str | None, str | None]:
    """Upload the normalized clip to the configured Supabase Storage bucket.

    Returns ``(bucket_key, error)``. Either may be None:
      - No bucket configured or demo mode → ``(None, None)``: local-only run.
      - Upload succeeds → ``(key, None)``.
      - Upload fails → ``(None, str(exc))``: the local normalized file is
        still valid; the frontend just can't stream it from the bucket until
        the upload is retried.

    Best-effort by design — the pipeline doesn't fail an otherwise-good
    ingest just because Storage is flaky.
    """
    if R.is_demo_mode() or not storage.bucket_configured("normalized"):
        return None, None
    key = f"{sha[:12]}.mp4"
    try:
        storage.upload_file(dst, key, kind="normalized")
    except Exception as exc:  # noqa: BLE001 — Supabase client raises many shapes
        log.warning("normalized upload failed for sha=%s: %s", sha[:12], exc)
        return None, str(exc)
    return key, None


__all__ = [
    "have_ffmpeg",
    "ingest_directory",
    "normalize_video",
    "probe_video",
    "sha256_file",
]
