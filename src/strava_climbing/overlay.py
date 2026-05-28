"""Pre-render per-attempt MP4 overlays with skeleton + CoM trail + metric HUD.

Reads the normalized video plus a cached :class:`pose.PoseTrack` array. Renders
with OpenCV directly — we already have the keypoints, so re-invoking the model
or going through ``supervision`` would just add overhead.

Streamlit never invokes inference at click time; it only ``st.video()``s the
files written here.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .boundary_detection import AttemptBounds
from .pose import PoseTrack

# COCO-17 skeleton edges
SKELETON_EDGES: tuple[tuple[int, int], ...] = (
    (5, 7), (7, 9),
    (6, 8), (8, 10),
    (5, 6),
    (5, 11), (6, 12),
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
    (0, 5), (0, 6),
)

SKELETON_COLOR = (60, 220, 60)
KEYPOINT_COLOR = (40, 250, 250)
TRAIL_COLOR = (0, 180, 255)
HUD_BG = (0, 0, 0)
HUD_FG = (255, 255, 255)
SEND_BADGE = (0, 200, 0)
FAIL_BADGE = (0, 100, 220)


@dataclass(slots=True, frozen=True)
class OverlayHUD:
    time_seconds: float
    smoothness_pct: float | None
    send: bool
    climber_name: str | None = None


def have_nvenc() -> bool:
    """Detect a usable NVENC encoder (requires an actual NVIDIA GPU at runtime).

    ffmpeg may advertise `h264_nvenc` because it was compiled with NVENC
    support, but encoding still fails on hosts without an NVIDIA card. Probe
    by attempting a 1-frame encode from a synthetic input.
    """
    if not shutil.which("ffmpeg"):
        return False
    try:
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=size=32x32:duration=0.1:rate=1",
                "-frames:v", "1", "-c:v", "h264_nvenc", "-f", "null", "-",
            ],
            check=True, capture_output=True, timeout=5,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def render_overlay(
    video_path: Path,
    track: PoseTrack,
    bounds: AttemptBounds,
    hud: OverlayHUD,
    out_path: Path,
    *,
    min_conf: float = 0.2,
) -> None:
    """Render ``[bounds.start_frame, bounds.end_frame]`` of ``video_path``
    with the climber's skeleton, CoM trail, and a metric HUD."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"overlay: failed to open {video_path}")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Write a temp .mp4 with libx264-friendly settings, then optionally
        # transcode with NVENC for the final file. (cv2's VideoWriter uses
        # mp4v which Streamlit may not play; ffmpeg pass-through fixes that.)
        tmp_path = out_path.with_suffix(".tmp.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(tmp_path), fourcc, fps, (w, h))
        if not writer.isOpened():
            raise RuntimeError(f"overlay: failed to open writer for {tmp_path}")

        cap.set(cv2.CAP_PROP_POS_FRAMES, bounds.start_frame)
        trail: list[tuple[int, int]] = []
        for f_idx in range(bounds.start_frame, bounds.end_frame):
            ok, frame = cap.read()
            if not ok:
                break
            if f_idx >= track.xy.shape[0]:
                writer.write(frame)
                continue

            _draw_skeleton(frame, track.xy[f_idx], track.conf[f_idx], min_conf)
            _update_trail(trail, track.com_xy[f_idx])
            _draw_trail(frame, trail)
            _draw_hud(
                frame,
                hud,
                progress=(f_idx - bounds.start_frame) / max(1, bounds.end_frame - bounds.start_frame),
                at_top=bounds.top_frame is not None and f_idx >= bounds.top_frame,
            )
            writer.write(frame)
        writer.release()
    finally:
        cap.release()

    _transcode(tmp_path, out_path)
    tmp_path.unlink(missing_ok=True)


def _transcode(src: Path, dst: Path) -> None:
    """ffmpeg-transcode the cv2 output to H.264 + faststart so Streamlit plays it.

    Tries NVENC first if the encoder is actually usable; falls back to libx264
    on any failure so we never end up with a 0-byte output on the FS.
    """
    encoder = "h264_nvenc" if have_nvenc() else "libx264"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-c:v", encoder,
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-movflags", "+faststart",
        "-an",
        str(dst),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        if encoder == "libx264":
            raise
        cmd[cmd.index("h264_nvenc")] = "libx264"
        subprocess.run(cmd, check=True, capture_output=True)


def _draw_skeleton(
    frame: np.ndarray, xy: np.ndarray, conf: np.ndarray, min_conf: float
) -> None:
    for a, b in SKELETON_EDGES:
        if conf[a] < min_conf or conf[b] < min_conf:
            continue
        pa = (int(xy[a, 0]), int(xy[a, 1]))
        pb = (int(xy[b, 0]), int(xy[b, 1]))
        cv2.line(frame, pa, pb, SKELETON_COLOR, 2, cv2.LINE_AA)
    for k in range(xy.shape[0]):
        if conf[k] < min_conf:
            continue
        p = (int(xy[k, 0]), int(xy[k, 1]))
        cv2.circle(frame, p, 3, KEYPOINT_COLOR, -1, cv2.LINE_AA)


def _update_trail(trail: list[tuple[int, int]], com: np.ndarray) -> None:
    if np.all(np.isfinite(com)):
        trail.append((int(com[0]), int(com[1])))


def _draw_trail(frame: np.ndarray, trail: list[tuple[int, int]]) -> None:
    if len(trail) < 2:
        return
    pts = np.asarray(trail, dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(frame, [pts], isClosed=False, color=TRAIL_COLOR, thickness=3, lineType=cv2.LINE_AA)


def _draw_hud(frame: np.ndarray, hud: OverlayHUD, progress: float, at_top: bool) -> None:
    h, w = frame.shape[:2]
    pad = 12
    box_h = 96
    box_w = 360 if hud.climber_name else 280
    overlay = frame.copy()
    cv2.rectangle(overlay, (pad, pad), (pad + box_w, pad + box_h), HUD_BG, -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

    y = pad + 26
    if hud.climber_name:
        cv2.putText(
            frame, hud.climber_name, (pad + 12, y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, HUD_FG, 2, cv2.LINE_AA,
        )
        y += 28

    cv2.putText(
        frame, f"{hud.time_seconds:5.1f}s", (pad + 12, y),
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, HUD_FG, 2, cv2.LINE_AA,
    )
    if hud.smoothness_pct is not None:
        cv2.putText(
            frame, f"smooth {hud.smoothness_pct:5.0f}", (pad + 140, y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, HUD_FG, 2, cv2.LINE_AA,
        )

    # Send/fail badge in the top-right.
    badge = "SEND" if hud.send else "ATTEMPT"
    badge_color = SEND_BADGE if hud.send else FAIL_BADGE
    if at_top and hud.send:
        badge = "TOPPED"
    (text_w, text_h), _ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
    bx2 = w - pad
    bx1 = bx2 - text_w - 24
    by1 = pad
    by2 = pad + text_h + 20
    cv2.rectangle(frame, (bx1, by1), (bx2, by2), badge_color, -1)
    cv2.putText(
        frame, badge, (bx1 + 12, by2 - 10),
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA,
    )

    # Progress bar across the bottom.
    bar_y = h - 8
    cv2.rectangle(frame, (0, bar_y), (w, h), (40, 40, 40), -1)
    cv2.rectangle(
        frame, (0, bar_y), (int(w * progress), h), TRAIL_COLOR, -1
    )


__all__ = ["OverlayHUD", "have_nvenc", "render_overlay"]
