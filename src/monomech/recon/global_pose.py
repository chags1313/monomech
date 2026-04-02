"""Floor alignment and contact-aware global pose estimation."""

from __future__ import annotations

import numpy as np

from ..config import GlobalPoseConfig
from ..constants import FOOT_LANDMARKS, LEFT_HIP, RIGHT_HIP
from ..types import PoseSequence3D
from ..utils.signal import moving_average


def _hip_center(xyz_frame: np.ndarray) -> np.ndarray | None:
    left = xyz_frame[LEFT_HIP]
    right = xyz_frame[RIGHT_HIP]
    if np.isfinite(left).all() and np.isfinite(right).all():
        return 0.5 * (left + right)
    if np.isfinite(left).all():
        return left.copy()
    if np.isfinite(right).all():
        return right.copy()
    return None


def _foot_floor(frame_xyz: np.ndarray, floor_quantile: float) -> float:
    ys = []
    for idx in FOOT_LANDMARKS:
        point = frame_xyz[idx]
        if np.isfinite(point[1]):
            ys.append(float(point[1]))
    if not ys:
        return 0.0
    return float(np.quantile(np.asarray(ys, dtype=float), floor_quantile))


def estimate_global_pose(source_pose: PoseSequence3D, config: GlobalPoseConfig) -> PoseSequence3D:
    xyz = source_pose.xyz.copy()
    n_frames = xyz.shape[0]

    # Floor-align Y first.
    floor_offsets = np.asarray([_foot_floor(xyz[i], config.floor_quantile) for i in range(n_frames)], dtype=float)
    floor_offsets = moving_average(floor_offsets, config.smoothing_window)
    xyz[:, :, 1] -= floor_offsets[:, None]

    # Contact-aware X/Z stabilization using feet close to floor with low speed.
    translations = np.zeros((n_frames, 3), dtype=float)
    anchors: dict[int, np.ndarray] = {}

    for i in range(1, n_frames):
        prev = xyz[i - 1] + translations[i - 1]
        curr = xyz[i]
        contact_offsets = []
        for idx in FOOT_LANDMARKS:
            p_curr = curr[idx]
            p_prev = prev[idx]
            if not np.isfinite(p_curr).all() or not np.isfinite(p_prev).all():
                anchors.pop(idx, None)
                continue
            vertical_ok = p_curr[1] <= config.contact_height_m
            released = p_curr[1] > config.contact_release_height_m
            speed = np.linalg.norm((p_curr - (xyz[i - 1, idx] + translations[i - 1])) / max(source_pose.time_s[i] - source_pose.time_s[i - 1], 1e-6))
            speed_ok = speed <= config.contact_speed_m_s
            if released:
                anchors.pop(idx, None)
                continue
            if vertical_ok and speed_ok:
                if idx not in anchors:
                    anchors[idx] = prev[idx, [0, 2]].copy()
                contact_offsets.append(anchors[idx] - p_curr[[0, 2]])
            else:
                anchors.pop(idx, None)
        if contact_offsets:
            mean_offset = np.mean(np.vstack(contact_offsets), axis=0)
            translations[i, 0] = mean_offset[0]
            translations[i, 2] = mean_offset[1]
        else:
            translations[i] = translations[i - 1]

    translations[:, 0] = moving_average(translations[:, 0], config.smoothing_window)
    translations[:, 2] = moving_average(translations[:, 2], config.smoothing_window)
    xyz += translations[:, None, :]

    return PoseSequence3D(
        time_s=source_pose.time_s.copy(),
        xyz=xyz,
        visibility=source_pose.visibility.copy(),
        metadata={**source_pose.metadata, "space": "global"},
    )
