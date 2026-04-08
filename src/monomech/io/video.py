from __future__ import annotations

import math
from pathlib import Path

from ..core.study import Study
from ..core.trials import VideoTrial


def _finite_number(value):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(value):
        return None
    return value


def probe_video(path: str | Path) -> dict:
    path = Path(path)

    # Prefer OpenCV for video probing. It is much more reliable for MP4
    # than letting imageio guess a plugin.
    try:
        import cv2  # type: ignore

        cap = cv2.VideoCapture(str(path))
        if cap.isOpened():
            fps = _finite_number(cap.get(cv2.CAP_PROP_FPS))
            nframes = _finite_number(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = _finite_number(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = _finite_number(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()

            fps = fps if fps and fps > 0 else None
            nframes_int = int(round(nframes)) if nframes and nframes > 0 else None
            duration = (nframes_int / fps) if (fps and nframes_int) else None
            size = (int(width), int(height)) if (width and height) else None

            if fps is not None or nframes_int is not None or size is not None:
                return {
                    "fps": fps,
                    "nframes": nframes_int,
                    "duration_s": duration,
                    "size": size,
                    "meta": {
                        "backend": "opencv",
                        "width": None if width is None else int(width),
                        "height": None if height is None else int(height),
                    },
                }
    except Exception:
        pass

    # Fallback to imageio only if OpenCV fails.
    try:
        import imageio.v3 as iio

        meta = iio.immeta(path)
        fps = _finite_number(meta.get("fps"))
        nframes = _finite_number(meta.get("nframes"))
        if nframes is None:
            nframes = _finite_number(meta.get("n_images"))

        duration = _finite_number(meta.get("duration"))
        if duration is None and fps is not None and nframes is not None and fps > 0:
            duration = nframes / fps

        return {
            "fps": fps,
            "nframes": int(round(nframes)) if nframes is not None else None,
            "duration_s": duration,
            "size": meta.get("size") or meta.get("shape"),
            "meta": meta,
        }
    except Exception:
        return {
            "fps": None,
            "nframes": None,
            "duration_s": None,
            "size": None,
            "meta": {"backend": "unknown"},
        }


def load_video(path: str | Path, *, name: str | None = None, metadata: dict | None = None) -> VideoTrial:
    path = Path(path)
    info = probe_video(path)
    return VideoTrial(
        name=name or path.stem,
        video_path=path,
        metadata={**info, **(metadata or {})},
    )


def load_videos(paths: list[str | Path], *, metadata: list[dict] | None = None) -> Study:
    trials = []
    for idx, path in enumerate(paths):
        md = metadata[idx] if metadata and idx < len(metadata) else None
        trials.append(load_video(path, metadata=md))
    return Study(trials=trials)