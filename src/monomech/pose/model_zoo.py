"""MediaPipe model helpers."""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path

from ..utils.files import ensure_dir


DEFAULT_POSE_MODEL_URLS = {
    "lite": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
    "full": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
    "heavy": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task",
}


def default_pose_model_url(variant: str = "heavy") -> str:
    return DEFAULT_POSE_MODEL_URLS.get(variant, DEFAULT_POSE_MODEL_URLS["heavy"])


def resolve_pose_model_asset(
    model_asset_path: str | None,
    *,
    model_variant: str = "heavy",
    allow_download: bool = True,
    cache_dir: str | None = None,
) -> Path:
    if model_asset_path:
        path = Path(model_asset_path)
        if not path.exists():
            raise FileNotFoundError(f"MediaPipe pose model not found: {path}")
        return path

    env_path = os.environ.get("MONOMECH_MEDIAPIPE_MODEL")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path

    cache_root = Path(cache_dir or (Path.home() / ".cache" / "monomech" / "models"))
    ensure_dir(cache_root)
    dst = cache_root / f"pose_landmarker_{model_variant}.task"
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    if not allow_download:
        raise FileNotFoundError(
            "No MediaPipe model asset was supplied. Provide model_asset_path or enable download."
        )
    url = default_pose_model_url(model_variant)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dst)
    return dst
