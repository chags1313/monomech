"""Video IO helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np


@dataclass(slots=True)
class VideoMetadata:
    path: Path
    fps: float
    width: int
    height: int
    n_frames: int | None
    duration_s: float | None


@dataclass(slots=True)
class VideoFrame:
    frame_index: int
    time_s: float
    bgr: np.ndarray


def open_video_metadata(path: str | Path) -> VideoMetadata:
    path = Path(path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {path}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        if not np.isfinite(fps) or fps <= 0:
            fps = 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        n_frames_raw = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        n_frames = int(n_frames_raw) if np.isfinite(n_frames_raw) and n_frames_raw > 0 else None
        duration_s = (n_frames / fps) if (n_frames is not None and fps > 0) else None
        return VideoMetadata(path=path, fps=fps, width=width, height=height, n_frames=n_frames, duration_s=duration_s)
    finally:
        cap.release()


def iter_video_frames(path: str | Path, target_fps: float | None = None, stride: int = 1) -> Iterator[VideoFrame]:
    meta = open_video_metadata(path)
    cap = cv2.VideoCapture(str(meta.path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {path}")
    frame_index = 0
    yielded = 0
    next_time = 0.0
    source_dt = 1.0 / meta.fps
    target_dt = (1.0 / target_fps) if (target_fps and target_fps > 0) else None
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if stride > 1 and frame_index % stride != 0:
                frame_index += 1
                continue
            time_s = frame_index * source_dt
            if target_dt is not None and time_s + 1e-9 < next_time:
                frame_index += 1
                continue
            yield VideoFrame(frame_index=frame_index, time_s=time_s, bgr=frame)
            yielded += 1
            if target_dt is not None:
                next_time = yielded * target_dt
            frame_index += 1
    finally:
        cap.release()
