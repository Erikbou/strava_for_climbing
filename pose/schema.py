"""Movement representation shared across the pipeline.

The 33-landmark BlazePose topology, the skeleton edges used for drawing, and a
`MovementSequence` container that is the reusable, serializable representation of a
climb. Downstream comparison/similarity features should consume this — not raw video.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict

import numpy as np

# BlazePose 33-landmark order (index -> name).
LANDMARK_NAMES: list[str] = [
    "nose",
    "left_eye_inner", "left_eye", "left_eye_outer",
    "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear",
    "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
    "left_pinky", "right_pinky",
    "left_index", "right_index",
    "left_thumb", "right_thumb",
    "left_hip", "right_hip",
    "left_knee", "right_knee",
    "left_ankle", "right_ankle",
    "left_heel", "right_heel",
    "left_foot_index", "right_foot_index",
]

LANDMARK_INDEX: dict[str, int] = {name: i for i, name in enumerate(LANDMARK_NAMES)}

NUM_LANDMARKS = len(LANDMARK_NAMES)  # 33

# Skeleton edges (pairs of landmark indices) for drawing the overlay.
POSE_CONNECTIONS: list[tuple[int, int]] = [
    # face
    (0, 1), (1, 2), (2, 3), (3, 7),
    (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10),
    # torso
    (11, 12), (11, 23), (12, 24), (23, 24),
    # left arm
    (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),
    # right arm
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
    # left leg
    (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),
    # right leg
    (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
]


@dataclass
class MovementSequence:
    """Per-frame pose landmarks for a single climb.

    Attributes:
        fps:    frames per second of the analyzed (work) video.
        width:  pixel width of the analyzed frames.
        height: pixel height of the analyzed frames.
        pixels: (N, 33, 3) image-space landmarks -> (x_px, y_px, visibility).
        world:  (N, 33, 3) hip-rooted 3D landmarks in meters, camera-invariant.
                This is the representation to use for cross-video comparison.
    """

    fps: float
    width: int
    height: int
    pixels: np.ndarray
    world: np.ndarray

    @property
    def num_frames(self) -> int:
        return int(self.pixels.shape[0])

    @property
    def times(self) -> np.ndarray:
        """Frame timestamps in seconds."""
        return np.arange(self.num_frames) / self.fps

    def save_npz(self, path: str) -> None:
        np.savez_compressed(
            path,
            pixels=self.pixels.astype(np.float32),
            world=self.world.astype(np.float32),
            fps=np.float32(self.fps),
            width=np.int32(self.width),
            height=np.int32(self.height),
        )

    def save_json(self, path: str) -> None:
        payload = {
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "num_frames": self.num_frames,
            "landmark_names": LANDMARK_NAMES,
            "pixels": np.round(self.pixels, 3).tolist(),
            "world": np.round(self.world, 5).tolist(),
        }
        with open(path, "w") as f:
            json.dump(payload, f)

    @classmethod
    def load_npz(cls, path: str) -> "MovementSequence":
        d = np.load(path)
        return cls(
            fps=float(d["fps"]),
            width=int(d["width"]),
            height=int(d["height"]),
            pixels=d["pixels"],
            world=d["world"],
        )
