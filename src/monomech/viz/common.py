from __future__ import annotations

from pathlib import Path
from typing import Sequence

import imageio.v3 as iio
import numpy as np

MEDIAPIPE_CONNECTIONS_33: list[tuple[int, int]] = [
    (0, 1), (1, 2), (2, 3),
    (0, 4), (4, 5), (5, 6),
    (9, 10),
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
    (15, 17), (15, 19), (15, 21),
    (16, 18), (16, 20), (16, 22),
    (11, 23), (12, 24),
    (23, 24),
    (23, 25), (25, 27),
    (24, 26), (26, 28),
    (27, 29), (29, 31),
    (28, 30), (30, 32),
]


def get_video_frame(video_path: str | Path, frame_idx: int) -> np.ndarray:
    return iio.imread(video_path, index=int(frame_idx))


def resolve_video_path(obj, video_path: str | Path | None = None) -> Path:
    if video_path is not None:
        return Path(video_path)

    metadata = getattr(obj, "metadata", None) or {}
    if "video_path" in metadata and metadata["video_path"]:
        return Path(metadata["video_path"])

    source_path = getattr(obj, "source_path", None)
    if source_path:
        return Path(source_path)

    raise ValueError("No video path found. Pass video_path=... explicitly.")


def get_connections(landmark_names: Sequence[str]) -> list[tuple[int, int]]:
    if len(landmark_names) == 33:
        return MEDIAPIPE_CONNECTIONS_33
    return []


def set_equal_3d_axes(ax, points: np.ndarray) -> None:
    if points.size == 0:
        return

    mins = np.nanmin(points, axis=0)
    maxs = np.nanmax(points, axis=0)
    center = (mins + maxs) / 2.0
    radius = np.nanmax(maxs - mins) / 2.0

    if not np.isfinite(radius) or radius <= 0:
        radius = 1.0

    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)