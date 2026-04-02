"""PnP-based root stabilization."""

from __future__ import annotations

import cv2
import numpy as np

from ..config import PnPConfig
from ..constants import PNP_PRIORITY_LANDMARKS
from ..types import PoseSequence2D, PoseSequence3D


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


def _solve_translation(world_xyz: np.ndarray, image_xy: np.ndarray, width: int, height: int, cfg: PnPConfig) -> np.ndarray | None:
    pairs = _gather_pairs(world_xyz, image_xy, np.ones((len(world_xyz),), dtype=float), cfg)
    if len(pairs) < cfg.min_points:
        return None
    object_points = []
    image_points = []
    for _, w, p, _ in pairs:
        object_points.append([-w[0], -w[1], -w[2]])
        image_points.append([p[0] * width, p[1] * height])
    object_points = np.asarray(object_points, dtype=np.float32)
    image_points = np.asarray(image_points, dtype=np.float32)

    camera_matrix = np.eye(3, dtype=np.float64)
    focal = width * cfg.focal_length_factor
    camera_matrix[0, 0] = focal
    camera_matrix[1, 1] = focal
    camera_matrix[0, 2] = width / 2.0
    camera_matrix[1, 2] = height / 2.0
    dist = np.zeros((4, 1), dtype=np.float64)

    rvec = np.zeros((3, 1), dtype=np.float64)
    tvec = np.zeros((3, 1), dtype=np.float64)

    ok = False
    if cfg.ransac and hasattr(cv2, "solvePnPRansac"):
        ok, rvec, tvec, _ = cv2.solvePnPRansac(
            object_points,
            image_points,
            camera_matrix,
            dist,
            rvec=rvec,
            tvec=tvec,
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
            rvec=rvec,
            tvec=tvec,
            useExtrinsicGuess=False,
            flags=cv2.SOLVEPNP_SQPNP,
        )
    if not ok:
        return None
    return np.asarray(tvec, dtype=float).reshape(3)


def compute_pnp_pose(
    pose2d: PoseSequence2D,
    world_pose: PoseSequence3D,
    *,
    frame_width: int,
    frame_height: int,
    config: PnPConfig,
) -> PoseSequence3D:
    xyz = world_pose.xyz.copy()
    out = xyz.copy()
    for frame_idx in range(world_pose.n_frames):
        frame_world = xyz[frame_idx]
        frame_2d = pose2d.xy[frame_idx]
        visibility = np.nan_to_num(world_pose.visibility[frame_idx], nan=0.0)
        pairs = _gather_pairs(frame_world, frame_2d, visibility, config)
        if len(pairs) < config.min_points:
            continue

        object_points = np.asarray([[-w[0], -w[1], -w[2]] for _, w, _, _ in pairs], dtype=np.float32)
        image_points = np.asarray([[p[0] * frame_width, p[1] * frame_height] for _, _, p, _ in pairs], dtype=np.float32)
        camera_matrix = np.eye(3, dtype=np.float64)
        focal = frame_width * config.focal_length_factor
        camera_matrix[0, 0] = focal
        camera_matrix[1, 1] = focal
        camera_matrix[0, 2] = frame_width / 2.0
        camera_matrix[1, 2] = frame_height / 2.0
        dist = np.zeros((4, 1), dtype=np.float64)

        ok = False
        if config.ransac and hasattr(cv2, "solvePnPRansac"):
            ok, rvec, tvec, _ = cv2.solvePnPRansac(
                object_points,
                image_points,
                camera_matrix,
                dist,
                useExtrinsicGuess=False,
                iterationsCount=config.iterations_count,
                reprojectionError=config.reprojection_error_px,
                confidence=config.confidence,
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
            continue
        tvec = np.asarray(tvec, dtype=float).reshape(3)
        for idx in range(out.shape[1]):
            p = frame_world[idx]
            if not np.isfinite(p).all():
                continue
            mx, my, mz = -p[0], -p[1], -p[2]
            wx, wy, wz = mx - tvec[0], my - tvec[1], mz - tvec[2]
            out[frame_idx, idx, 0] = -wx
            out[frame_idx, idx, 1] = -wy
            out[frame_idx, idx, 2] = -wz

    return PoseSequence3D(
        time_s=world_pose.time_s.copy(),
        xyz=out,
        visibility=world_pose.visibility.copy(),
        metadata={**world_pose.metadata, "space": "pnp"},
    )
