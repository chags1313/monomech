"""Modular 2D pose stage."""

from __future__ import annotations

from ._shared import ensure_mediapipe_extraction, ensure_trial, stage_metadata
from .config import MediaPipePoseConfig
from .results import Pose2DResult
from .tables import pose2d_long_table, pose2d_wide_table, simple_pose_summary, visibility_summary_table
from .visualization.plotly import make_pose_2d_figure


def process(trial, *, config: MediaPipePoseConfig | None = None, refresh: bool = False) -> Pose2DResult:
    trial = ensure_trial(trial)
    extraction = ensure_mediapipe_extraction(trial, config=config, refresh=refresh)
    sequence = extraction.pose2d
    if sequence is None:
        raise RuntimeError("MediaPipe extraction did not produce pose2d data.")

    long_df = pose2d_long_table(sequence)
    wide_df = pose2d_wide_table(sequence)
    summary_df = simple_pose_summary(sequence, stage="pose2d")
    visibility_df = visibility_summary_table(sequence.visibility, stage="pose2d")
    result = Pose2DResult(
        stage="pose2d",
        sequence=sequence,
        df=long_df,
        tables={
            "landmarks_long": long_df,
            "landmarks_wide": wide_df,
            "summary": summary_df,
            "visibility": visibility_df,
        },
        meta=stage_metadata(trial, source="mediapipe.pose_landmarks"),
        figures={"pose2d": make_pose_2d_figure(extraction)},
    )
    return trial.register_stage("pose2d", result)
