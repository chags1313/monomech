"""Modular world3d stage backed directly by MediaPipe pose world landmarks."""

from __future__ import annotations

from ._shared import ensure_mediapipe_extraction, ensure_trial, stage_metadata
from .config import MediaPipePoseConfig
from .results import World3DResult
from .tables import pose3d_long_table, pose3d_wide_table, segment_length_table, simple_pose_summary, visibility_summary_table
from .visualization.plotly import make_joint_trace_figure, make_pose_3d_figure


def process(trial, *, pose2d=None, config: MediaPipePoseConfig | None = None, refresh: bool = False) -> World3DResult:
    trial = ensure_trial(trial)
    extraction = ensure_mediapipe_extraction(trial, config=config, refresh=refresh)
    sequence = extraction.world_pose
    if sequence is None:
        raise RuntimeError("MediaPipe extraction did not produce pose world landmarks.")

    long_df = pose3d_long_table(sequence, source="world3d")
    wide_df = pose3d_wide_table(sequence)
    summary_df = simple_pose_summary(sequence, stage="world3d")
    segment_df = segment_length_table(sequence)
    visibility_df = visibility_summary_table(sequence.visibility, stage="world3d")
    result = World3DResult(
        stage="world3d",
        sequence=sequence,
        df=long_df,
        tables={
            "world3d_long": long_df,
            "world3d_wide": wide_df,
            "segment_lengths": segment_df,
            "summary": summary_df,
            "visibility": visibility_df,
        },
        meta=stage_metadata(
            trial,
            source="mediapipe.pose_world_landmarks",
            root_centered=True,
            depends_on=["pose2d", "world3d_raw"],
        ),
        figures={
            "world3d": make_pose_3d_figure(extraction, coordinate_set="world"),
            "joint_trace": make_joint_trace_figure(extraction, coordinate_set="world"),
        },
    )
    return trial.register_stage("world3d", result)
