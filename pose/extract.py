"""Video -> MovementSequence.

Pre-transcodes the source to a manageable working clip (longest side capped,
fps reduced) with ffmpeg, then runs MediaPipe Pose Landmarker in VIDEO mode to
produce per-frame 2D pixel and 3D world landmarks.
"""

from __future__ import annotations

import subprocess

import cv2
import numpy as np

from .schema import NUM_LANDMARKS, MovementSequence


def transcode(src: str, dst: str, max_dim: int = 1280, fps: int = 30) -> str:
    """Downscale + resample `src` to `dst` (H.264, no audio). Returns `dst`.

    The longest side is capped to `max_dim` (aspect preserved, even dims) and
    the frame rate set to `fps`. iPhone rotation metadata is baked in by ffmpeg
    so the output is upright.
    """
    w_expr = f"if(gt(iw,ih),min({max_dim},iw),-2)"
    h_expr = f"if(gt(iw,ih),-2,min({max_dim},ih))"
    vf = f"fps={fps},scale='{w_expr}':'{h_expr}'"
    cmd = [
        "ffmpeg", "-y", "-i", src,
        "-vf", vf,
        "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        dst,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return dst


def _forward_back_fill(arr: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Replace frames where `valid` is False by carrying the nearest valid frame."""
    n = arr.shape[0]
    if not valid.any():
        return np.nan_to_num(arr)
    last = None
    for i in range(n):  # forward fill
        if valid[i]:
            last = arr[i]
        elif last is not None:
            arr[i] = last
    nxt = None
    for i in range(n - 1, -1, -1):  # back fill leading gap
        if valid[i]:
            nxt = arr[i]
        elif nxt is not None and not valid[i]:
            arr[i] = nxt
    return arr


def extract_pose(video_path: str, model_path: str) -> MovementSequence:
    """Run pose estimation over every frame of `video_path`."""
    # Import here so the module imports cheaply even without mediapipe present.
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    options = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=model_path),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
    )

    pixels: list[np.ndarray] = []
    world: list[np.ndarray] = []
    valid: list[bool] = []

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts_ms = int(idx * 1000.0 / fps)
            result = landmarker.detect_for_video(mp_image, ts_ms)

            px = np.full((NUM_LANDMARKS, 3), np.nan, dtype=np.float32)
            wd = np.full((NUM_LANDMARKS, 3), np.nan, dtype=np.float32)
            has = bool(result.pose_landmarks)
            if has:
                lms = result.pose_landmarks[0]
                wlms = result.pose_world_landmarks[0]
                for j, lm in enumerate(lms):
                    px[j] = (lm.x * width, lm.y * height, lm.visibility)
                for j, wl in enumerate(wlms):
                    wd[j] = (wl.x, wl.y, wl.z)
            pixels.append(px)
            world.append(wd)
            valid.append(has)
            idx += 1

    cap.release()

    pixels_arr = np.stack(pixels) if pixels else np.zeros((0, NUM_LANDMARKS, 3), np.float32)
    world_arr = np.stack(world) if world else np.zeros((0, NUM_LANDMARKS, 3), np.float32)
    valid_arr = np.array(valid, dtype=bool)
    pixels_arr = _forward_back_fill(pixels_arr, valid_arr)
    world_arr = _forward_back_fill(world_arr, valid_arr)

    detected = int(valid_arr.sum())
    print(f"  pose detected in {detected}/{len(valid)} frames")
    return MovementSequence(
        fps=float(fps), width=width, height=height,
        pixels=pixels_arr, world=world_arr,
    )
