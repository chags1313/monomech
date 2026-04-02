"""Modular global pose stage using pose2d + world3d + pnp."""

from __future__ import annotations

from ._shared import ensure_trial, stage_metadata
from .config import GlobalPoseConfig
from .recon.global_pose import estimate_global_pose as _estimate_global_pose
from .results import GlobalPoseResult
from .tables import contact_table, floor_table_from_source, pose3d_long_table, pose3d_wide_table, root_trajectory_table, simple_pose_summary
from .types import TrialResult
from .visualization.plotly import make_joint_trace_figure, make_pose_3d_figure


def estimate(trial, *, pose2d, world3d, pnp, config: GlobalPoseConfig | None = None) -> GlobalPoseResult:
    trial = ensure_trial(trial)
    cfg = config or GlobalPoseConfig()
    pnp_seq = pnp.sequence if hasattr(pnp, "sequence") else pnp
    pose2d_seq = pose2d.sequence if hasattr(pose2d, "sequence") else pose2d
    world3d_seq = world3d.sequence if hasattr(world3d, "sequence") else world3d

    sequence = _estimate_global_pose(pnp_seq, cfg)
    long_df = pose3d_long_table(sequence, source="global_pose")
    wide_df = pose3d_wide_table(sequence)
    contacts_df = contact_table(sequence, cfg.contact_height_m)
    floor_df = floor_table_from_source(pnp_seq, cfg.floor_quantile)
    root_df = root_trajectory_table(sequence)
    summary_df = simple_pose_summary(sequence, stage="global_pose")
    summary_df["left_contact_fraction"] = float(contacts_df["left_contact"].mean()) if not contacts_df.empty else 0.0
    summary_df["right_contact_fraction"] = float(contacts_df["right_contact"].mean()) if not contacts_df.empty else 0.0
    summary_df["mean_floor_y"] = float(floor_df["estimated_floor_y"].mean(skipna=True)) if not floor_df.empty else 0.0

    trial_for_figs = TrialResult(
        name=trial.name,
        video_path=trial.video_path,
        fps=trial.fps,
        pose2d=pose2d_seq,
        world_pose=world3d_seq,
        pnp_pose=pnp_seq,
        global_pose=sequence,
        metadata={"width": trial.width, "height": trial.height, **trial.metadata},
    )

    result = GlobalPoseResult(
        stage="global_pose",
        sequence=sequence,
        df=long_df,
        tables={
            "global_pose_long": long_df,
            "global_pose_wide": wide_df,
            "contacts": contacts_df,
            "floor": floor_df,
            "root_trajectory": root_df,
            "summary": summary_df,
        },
        meta=stage_metadata(trial, depends_on=["pose2d", "world3d", "pnp"]),
        figures={
            "global_pose": make_pose_3d_figure(trial_for_figs, coordinate_set="global"),
            "joint_trace": make_joint_trace_figure(trial_for_figs, coordinate_set="global"),
        },
    )
    return trial.register_stage("global_pose", result)
