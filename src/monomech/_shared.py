"""Internal helpers shared by modular stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import MediaPipePoseConfig
from .pose.mediapipe_backend import MediaPipePoseEstimator
from .trial import Trial
from .types import PoseSequence3D, TrialResult


def ensure_trial(value: Trial | str | Path) -> Trial:
    if isinstance(value, Trial):
        return value
    return Trial.from_video(value)


def ensure_mediapipe_extraction(trial: Trial, config: MediaPipePoseConfig | None = None, refresh: bool = False) -> TrialResult:
    if trial._mediapipe_extraction is not None and not refresh:
        return trial._mediapipe_extraction
    cfg = config or MediaPipePoseConfig()
    extraction = MediaPipePoseEstimator(cfg).process_video(trial.video_path)
    trial._mediapipe_extraction = extraction
    trial.fps = extraction.fps
    trial.metadata.update(extraction.metadata)
    return extraction


def trial_result_from_global(trial: Trial, pose: PoseSequence3D) -> TrialResult:
    return TrialResult(
        name=trial.name,
        video_path=trial.video_path,
        fps=trial.fps,
        global_pose=pose,
        metadata={"width": trial.width, "height": trial.height, **trial.metadata},
    )


def stage_metadata(trial: Trial, **extra: Any) -> dict[str, Any]:
    return {
        "trial_name": trial.name,
        "video_path": str(trial.video_path),
        "fps": trial.fps,
        "width": trial.width,
        "height": trial.height,
        "duration_s": trial.duration_s,
        **extra,
    }
