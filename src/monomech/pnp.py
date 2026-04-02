"""Modular PnP stage using pose2d + world3d."""

from __future__ import annotations

import cv2
import numpy as np
import pandas as pd

from ._shared import ensure_trial, stage_metadata
from .config import PnPConfig
from .constants import PNP_PRIORITY_LANDMARKS
from .results import PnPResult
from .tables import pose3d_long_table, pose3d_wide_table, simple_pose_summary
from .types import PoseSequence2D, PoseSequence3D, TrialResult
from .visualization.plotly import make_joint_trace_figure, make_pose_3d_figure


def _gather_pairs(world_xyz: np.ndarray, image_xy: np.ndarray, visibility: np.ndarray, cfg: PnPConfig):
    preferred = []
    fallback = []
    preferred_set = set(PNP_PRIORITY_LANDMARKS)
    n = min(len(world_xyz), len(image_xy), len(visibility))
    for idx in range(n):
        w = world_xyz[idx]
        p = image_xy[idx]
        vis = visibility[idx]
        if not np.isfinite(w).all() or not np.isfinite(p).all() or not np.isfinite(vis):
            continue
        if p[0] < -0.10 or p[0] > 1.10 or p[1] < -0.10 or p[1] > 1.10:
            continue
        if vis < cfg.min_visibility:
            continue
        item = (idx, w, p, float(vis) + (0.3 if idx in preferred_set else 0.0))
        (preferred if idx in preferred_set else fallback).append(item)
    preferred.sort(key=lambda x: x[3], reverse=True)
    fallback.sort(key=lambda x: x[3], reverse=True)
    return (preferred + fallback)[: cfg.max_points]


def _project_points(object_points: np.ndarray, rvec: np.ndarray, tvec: np.ndarray, camera_matrix: np.ndarray, dist: np.ndarray) -> np.ndarray:
    projected, _ = cv2.projectPoints(object_points, rvec, tvec, camera_matrix, dist)
    return projected.reshape(-1, 2)


def solve(trial, *, pose2d, world3d, config: PnPConfig | None = None) -> PnPResult:
    trial = ensure_trial(trial)
    cfg = config or PnPConfig()
    pose2d_seq: PoseSequence2D = pose2d.sequence if hasattr(pose2d, "sequence") else pose2d
    world3d_seq: PoseSequence3D = world3d.sequence if hasattr(world3d, "sequence") else world3d

    out = world3d_seq.xyz.copy()
    camera_rows: list[dict[str, float]] = []
    reprojection_rows: list[dict[str, float]] = []

    for frame_idx in range(world3d_seq.n_frames):
        frame_world = world3d_seq.xyz[frame_idx]
        frame_2d = pose2d_seq.xy[frame_idx]
        visibility = np.nan_to_num(world3d_seq.visibility[frame_idx], nan=0.0)
        pairs = _gather_pairs(frame_world, frame_2d, visibility, cfg)
        camera_row = {
            "frame": frame_idx,
            "time": float(world3d_seq.time_s[frame_idx]),
            "success": False,
            "n_points": len(pairs),
            "rvec_x": np.nan,
            "rvec_y": np.nan,
            "rvec_z": np.nan,
            "tvec_x": np.nan,
            "tvec_y": np.nan,
            "tvec_z": np.nan,
            "mean_reprojection_error_px": np.nan,
        }
        if len(pairs) < cfg.min_points:
            camera_rows.append(camera_row)
            continue
        object_points = np.asarray([[-w[0], -w[1], -w[2]] for _, w, _, _ in pairs], dtype=np.float32)
        image_points = np.asarray([[p[0] * trial.width, p[1] * trial.height] for _, _, p, _ in pairs], dtype=np.float32)
        camera_matrix = np.eye(3, dtype=np.float64)
        focal = trial.width * cfg.focal_length_factor
        camera_matrix[0, 0] = focal
        camera_matrix[1, 1] = focal
        camera_matrix[0, 2] = trial.width / 2.0
        camera_matrix[1, 2] = trial.height / 2.0
        dist = np.zeros((4, 1), dtype=np.float64)

        ok = False
        if cfg.ransac and hasattr(cv2, "solvePnPRansac"):
            ok, rvec, tvec, _ = cv2.solvePnPRansac(
                object_points,
                image_points,
                camera_matrix,
                dist,
                useExtrinsicGuess=False,
                iterationsCount=cfg.iterations_count,
                reprojectionError=cfg.reprojection_error_px,
                confidence=cfg.confidence,
                flags=cv2.SOLVEPNP_EPNP,
            )
        if not ok:
            ok, rvec, tvec = cv2.solvePnP(
                object_points,
                image_points,
                camera_matrix,
                dist,
                useExtrinsicGuess=False,
                flags=cv2.SOLVEPNP_SQPNP,
            )
        if not ok:
            camera_rows.append(camera_row)
            continue

        tvec = np.asarray(tvec, dtype=float).reshape(3)
        rvec = np.asarray(rvec, dtype=float).reshape(3)
        for idx in range(out.shape[1]):
            p = frame_world[idx]
            if not np.isfinite(p).all():
                continue
            mx, my, mz = -p[0], -p[1], -p[2]
            wx = mx - tvec[0]
            wy = my - tvec[1]
            wz = mz - tvec[2]
            out[frame_idx, idx, 0] = -wx
            out[frame_idx, idx, 1] = -wy
            out[frame_idx, idx, 2] = -wz

        projected = _project_points(object_points, rvec.reshape(3, 1), tvec.reshape(3, 1), camera_matrix, dist)
        errors = np.linalg.norm(projected - image_points, axis=1)
        for pair_idx, (joint_idx, _, _, _) in enumerate(pairs):
            reprojection_rows.append(
                {
                    "frame": frame_idx,
                    "time": float(world3d_seq.time_s[frame_idx]),
                    "joint_index": joint_idx,
                    "observed_x_px": float(image_points[pair_idx, 0]),
                    "observed_y_px": float(image_points[pair_idx, 1]),
                    "projected_x_px": float(projected[pair_idx, 0]),
                    "projected_y_px": float(projected[pair_idx, 1]),
                    "reprojection_error_px": float(errors[pair_idx]),
                }
            )
        camera_row.update(
            {
                "success": True,
                "rvec_x": float(rvec[0]),
                "rvec_y": float(rvec[1]),
                "rvec_z": float(rvec[2]),
                "tvec_x": float(tvec[0]),
                "tvec_y": float(tvec[1]),
                "tvec_z": float(tvec[2]),
                "mean_reprojection_error_px": float(np.mean(errors)) if len(errors) else np.nan,
            }
        )
        camera_rows.append(camera_row)

    sequence = PoseSequence3D(
        time_s=world3d_seq.time_s.copy(),
        xyz=out,
        visibility=world3d_seq.visibility.copy(),
        metadata={**world3d_seq.metadata, "space": "pnp"},
    )
    camera_df = pd.DataFrame(camera_rows)
    reprojection_df = pd.DataFrame(reprojection_rows)
    summary_df = simple_pose_summary(sequence, stage="pnp")
    if not camera_df.empty:
        summary_df["solve_success_rate"] = float(camera_df["success"].mean())
        summary_df["mean_reprojection_error_px"] = float(camera_df["mean_reprojection_error_px"].mean(skipna=True))
    long_df = pose3d_long_table(sequence, source="pnp")
    wide_df = pose3d_wide_table(sequence)
    trial_for_figs = TrialResult(
        name=trial.name,
        video_path=trial.video_path,
        fps=trial.fps,
        pose2d=pose2d_seq,
        world_pose=world3d_seq,
        pnp_pose=sequence,
        metadata={"width": trial.width, "height": trial.height, **trial.metadata},
    )
    result = PnPResult(
        stage="pnp",
        sequence=sequence,
        df=camera_df,
        tables={
            "camera_pose": camera_df,
            "reprojection": reprojection_df,
            "pnp_long": long_df,
            "pnp_wide": wide_df,
            "summary": summary_df,
        },
        meta=stage_metadata(trial, depends_on=["pose2d", "world3d"]),
        figures={
            "pnp_pose": make_pose_3d_figure(trial_for_figs, coordinate_set="pnp"),
            "joint_trace": make_joint_trace_figure(trial_for_figs, coordinate_set="pnp"),
        },
    )
    return trial.register_stage("pnp", result)
