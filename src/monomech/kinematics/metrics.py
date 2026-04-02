"""Kinematic summary metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..constants import LANDMARK_INDEX
from ..types import PoseSequence3D
from ..utils.math3d import angle_deg


DEFAULT_ANGLE_DEFINITIONS = {
    "left_elbow": ("left_shoulder", "left_elbow", "left_wrist"),
    "right_elbow": ("right_shoulder", "right_elbow", "right_wrist"),
    "left_knee": ("left_hip", "left_knee", "left_ankle"),
    "right_knee": ("right_hip", "right_knee", "right_ankle"),
    "left_hip": ("left_shoulder", "left_hip", "left_knee"),
    "right_hip": ("right_shoulder", "right_hip", "right_knee"),
}


def compute_joint_angle_trace(pose: PoseSequence3D, a: str, b: str, c: str) -> np.ndarray:
    ia, ib, ic = LANDMARK_INDEX[a], LANDMARK_INDEX[b], LANDMARK_INDEX[c]
    out = np.full((pose.n_frames,), np.nan, dtype=float)
    for idx in range(pose.n_frames):
        pa, pb, pc = pose.xyz[idx, ia], pose.xyz[idx, ib], pose.xyz[idx, ic]
        if not np.isfinite(pa).all() or not np.isfinite(pb).all() or not np.isfinite(pc).all():
            continue
        out[idx] = angle_deg(pa, pb, pc)
    return out


def compute_linear_velocity_trace(pose: PoseSequence3D, landmark: str) -> np.ndarray:
    idx = LANDMARK_INDEX[landmark]
    xyz = pose.xyz[:, idx, :]
    dt = np.gradient(pose.time_s)
    dt = np.where(np.abs(dt) < 1e-9, 1.0, dt)
    vx = np.gradient(xyz[:, 0], pose.time_s)
    vy = np.gradient(xyz[:, 1], pose.time_s)
    vz = np.gradient(xyz[:, 2], pose.time_s)
    speed = np.sqrt(vx**2 + vy**2 + vz**2)
    speed[~np.isfinite(speed)] = np.nan
    return speed


def compute_default_angle_traces(pose: PoseSequence3D) -> pd.DataFrame:
    rows = {"time": pose.time_s}
    for label, (a, b, c) in DEFAULT_ANGLE_DEFINITIONS.items():
        rows[label] = compute_joint_angle_trace(pose, a, b, c)
    return pd.DataFrame(rows)
