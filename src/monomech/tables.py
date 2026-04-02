"""Table builders for stage outputs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

from .constants import FOOT_LANDMARKS, LANDMARK_NAMES, LEFT_HIP, RIGHT_HIP, POSE_CONNECTIONS
from .types import PoseSequence2D, PoseSequence3D


def _rows_to_df(rows: list[dict[str, Any]], columns: Iterable[str] | None = None) -> pd.DataFrame:
    if rows:
        return pd.DataFrame(rows)
    if columns is None:
        return pd.DataFrame()
    return pd.DataFrame(columns=list(columns))


def pose2d_long_table(sequence: PoseSequence2D) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for frame_idx, t in enumerate(sequence.time_s):
        for joint_idx, joint in enumerate(LANDMARK_NAMES[: sequence.n_landmarks]):
            rows.append(
                {
                    "frame": frame_idx,
                    "time": float(t),
                    "joint": joint,
                    "joint_index": joint_idx,
                    "x": float(sequence.xy[frame_idx, joint_idx, 0]),
                    "y": float(sequence.xy[frame_idx, joint_idx, 1]),
                    "visibility": float(sequence.visibility[frame_idx, joint_idx]),
                }
            )
    return _rows_to_df(rows, ["frame", "time", "joint", "joint_index", "x", "y", "visibility"])


def pose2d_wide_table(sequence: PoseSequence2D) -> pd.DataFrame:
    df = sequence.to_dataframe().copy()
    df.insert(0, "frame", np.arange(len(df)))
    return df


def pose3d_long_table(sequence: PoseSequence3D, *, source: str | None = None) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for frame_idx, t in enumerate(sequence.time_s):
        for joint_idx, joint in enumerate(LANDMARK_NAMES[: sequence.n_landmarks]):
            rows.append(
                {
                    "frame": frame_idx,
                    "time": float(t),
                    "joint": joint,
                    "joint_index": joint_idx,
                    "x": float(sequence.xyz[frame_idx, joint_idx, 0]),
                    "y": float(sequence.xyz[frame_idx, joint_idx, 1]),
                    "z": float(sequence.xyz[frame_idx, joint_idx, 2]),
                    "visibility": float(sequence.visibility[frame_idx, joint_idx]),
                    "source": source,
                }
            )
    return _rows_to_df(rows, ["frame", "time", "joint", "joint_index", "x", "y", "z", "visibility", "source"])


def pose3d_wide_table(sequence: PoseSequence3D) -> pd.DataFrame:
    df = sequence.to_dataframe().copy()
    df.insert(0, "frame", np.arange(len(df)))
    return df


def visibility_summary_table(visibility: np.ndarray, *, stage: str) -> pd.DataFrame:
    rows = []
    for idx, joint in enumerate(LANDMARK_NAMES[: visibility.shape[1]]):
        col = visibility[:, idx]
        rows.append(
            {
                "stage": stage,
                "joint": joint,
                "mean_visibility": float(np.nanmean(col)),
                "min_visibility": float(np.nanmin(col)),
                "max_visibility": float(np.nanmax(col)),
                "missing_fraction": float(np.mean(~np.isfinite(col))),
            }
        )
    return pd.DataFrame(rows)


def segment_length_table(sequence: PoseSequence3D) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    segments = [(a, b) for a, b in POSE_CONNECTIONS if a < sequence.n_landmarks and b < sequence.n_landmarks]
    for frame_idx, t in enumerate(sequence.time_s):
        for a, b in segments:
            pa = sequence.xyz[frame_idx, a]
            pb = sequence.xyz[frame_idx, b]
            if np.isfinite(pa).all() and np.isfinite(pb).all():
                length = float(np.linalg.norm(pb - pa))
            else:
                length = np.nan
            rows.append(
                {
                    "frame": frame_idx,
                    "time": float(t),
                    "segment": f"{LANDMARK_NAMES[a]}__{LANDMARK_NAMES[b]}",
                    "length": length,
                }
            )
    return pd.DataFrame(rows)


def simple_pose_summary(sequence: PoseSequence2D | PoseSequence3D, *, stage: str) -> pd.DataFrame:
    n_coords = 2 if isinstance(sequence, PoseSequence2D) else 3
    visibility = sequence.visibility
    return pd.DataFrame(
        [
            {
                "stage": stage,
                "n_frames": int(sequence.n_frames),
                "n_landmarks": int(sequence.n_landmarks),
                "n_coordinates": n_coords,
                "time_start": float(sequence.time_s[0]),
                "time_end": float(sequence.time_s[-1]),
                "mean_visibility": float(np.nanmean(visibility)),
            }
        ]
    )


def root_trajectory_table(sequence: PoseSequence3D) -> pd.DataFrame:
    rows = []
    for frame_idx, t in enumerate(sequence.time_s):
        left = sequence.xyz[frame_idx, LEFT_HIP]
        right = sequence.xyz[frame_idx, RIGHT_HIP]
        if np.isfinite(left).all() and np.isfinite(right).all():
            root = 0.5 * (left + right)
        elif np.isfinite(left).all():
            root = left
        elif np.isfinite(right).all():
            root = right
        else:
            root = np.array([np.nan, np.nan, np.nan], dtype=float)
        rows.append(
            {
                "frame": frame_idx,
                "time": float(t),
                "root_x": float(root[0]),
                "root_y": float(root[1]),
                "root_z": float(root[2]),
            }
        )
    return pd.DataFrame(rows)


def contact_table(sequence: PoseSequence3D, contact_height_m: float) -> pd.DataFrame:
    rows = []
    left_ids = [idx for idx in FOOT_LANDMARKS if "left" in LANDMARK_NAMES[idx]]
    right_ids = [idx for idx in FOOT_LANDMARKS if "right" in LANDMARK_NAMES[idx]]
    for frame_idx, t in enumerate(sequence.time_s):
        left_y = [sequence.xyz[frame_idx, idx, 1] for idx in left_ids if np.isfinite(sequence.xyz[frame_idx, idx, 1])]
        right_y = [sequence.xyz[frame_idx, idx, 1] for idx in right_ids if np.isfinite(sequence.xyz[frame_idx, idx, 1])]
        left_contact = bool(left_y and np.nanmin(left_y) <= contact_height_m)
        right_contact = bool(right_y and np.nanmin(right_y) <= contact_height_m)
        rows.append(
            {
                "frame": frame_idx,
                "time": float(t),
                "left_contact": left_contact,
                "right_contact": right_contact,
                "left_foot_min_y": float(np.nanmin(left_y)) if left_y else np.nan,
                "right_foot_min_y": float(np.nanmin(right_y)) if right_y else np.nan,
            }
        )
    return pd.DataFrame(rows)


def floor_table_from_source(source_pose: PoseSequence3D, floor_quantile: float) -> pd.DataFrame:
    rows = []
    for frame_idx, t in enumerate(source_pose.time_s):
        foot_y = [source_pose.xyz[frame_idx, idx, 1] for idx in FOOT_LANDMARKS if np.isfinite(source_pose.xyz[frame_idx, idx, 1])]
        floor_y = float(np.quantile(np.asarray(foot_y, dtype=float), floor_quantile)) if foot_y else np.nan
        rows.append({"frame": frame_idx, "time": float(t), "estimated_floor_y": floor_y})
    return pd.DataFrame(rows)
