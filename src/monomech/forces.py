"""Notebook-friendly external force definitions and force-set stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

import numpy as np
import pandas as pd

from ._shared import ensure_trial, stage_metadata
from .constants import LANDMARK_INDEX
from .results import ForceSetResult
from .types import ExternalForceSpec, PoseSequence3D

VectorLike = tuple[float, float, float] | list[float] | np.ndarray | pd.DataFrame | Callable[[Any, int, float], tuple[float, float, float]]
PointLike = VectorLike | str

DEFAULT_SEGMENT_MAP = {
    "right_foot": "calcn_r",
    "left_foot": "calcn_l",
    "right_toes": "toes_r",
    "left_toes": "toes_l",
    "right_shank": "tibia_r",
    "left_shank": "tibia_l",
    "right_talus": "talus_r",
    "left_talus": "talus_l",
    "right_thigh": "femur_r",
    "left_thigh": "femur_l",
    "pelvis": "pelvis",
    "sacrum": "sacrum",
    "trunk": "torso",
    "torso": "torso",
    "abdomen": "Abdomen",
    "head": "head",
    "right_upper_arm": "humerus_r",
    "left_upper_arm": "humerus_l",
    "right_forearm": "radius_r",
    "left_forearm": "radius_l",
    "right_hand": "hand_r",
    "left_hand": "hand_l",
}

SEGMENT_LANDMARKS = {
    "right_foot": ["right_ankle", "right_heel", "right_foot_index"],
    "left_foot": ["left_ankle", "left_heel", "left_foot_index"],
    "right_shank": ["right_knee", "right_ankle"],
    "left_shank": ["left_knee", "left_ankle"],
    "right_thigh": ["right_hip", "right_knee"],
    "left_thigh": ["left_hip", "left_knee"],
    "pelvis": ["left_hip", "right_hip"],
    "trunk": ["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
    "right_hand": ["right_wrist", "right_index", "right_pinky"],
    "left_hand": ["left_wrist", "left_index", "left_pinky"],
}


@dataclass(slots=True)
class ExternalForce:
    name: str
    target: str
    force: VectorLike | None = None
    point: PointLike | None = None
    torque: VectorLike | None = None
    applied_to_body: str | None = None
    magnitude: float | None = None
    direction: tuple[float, float, float] | None = None
    start_time: float | None = None
    end_time: float | None = None
    reference_frame: str = "ground"
    point_expressed_in_body: str = "ground"
    notes: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def constant(
        cls,
        *,
        name: str,
        target: str,
        magnitude: float,
        direction: tuple[float, float, float],
        point: PointLike,
        applied_to_body: str | None = None,
        torque: VectorLike | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> "ExternalForce":
        return cls(
            name=name,
            target=target,
            magnitude=magnitude,
            direction=direction,
            point=point,
            torque=torque,
            applied_to_body=applied_to_body,
            start_time=start_time,
            end_time=end_time,
        )


@dataclass(slots=True)
class ForceSet:
    forces: list[ExternalForce]

    def __iter__(self):
        return iter(self.forces)

    def __len__(self) -> int:
        return len(self.forces)


def _normalize_vector(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm < 1e-12:
        raise ValueError("Direction vector must be non-zero.")
    return vec / norm


def _vector_from_provider(provider: VectorLike | None, trial, frame_idx: int, time_s: float) -> np.ndarray:
    if provider is None:
        return np.zeros(3, dtype=float)
    if callable(provider):
        value = provider(trial, frame_idx, time_s)
        return np.asarray(value, dtype=float).reshape(3)
    if isinstance(provider, pd.DataFrame):
        cols = [c for c in provider.columns if c.lower() in {"x", "y", "z", "fx", "fy", "fz", "px", "py", "pz", "tx", "ty", "tz"}]
        if len(cols) < 3:
            raise ValueError("DataFrame providers must include three coordinate columns.")
        return provider.iloc[frame_idx][cols[:3]].to_numpy(dtype=float)
    arr = np.asarray(provider, dtype=float)
    if arr.ndim == 2:
        return arr[frame_idx].reshape(3)
    return arr.reshape(3)


def _resolve_semantic_point(point: str, pose: PoseSequence3D, frame_idx: int) -> np.ndarray:
    if point in LANDMARK_INDEX:
        return pose.xyz[frame_idx, LANDMARK_INDEX[point]].astype(float)
    if point in SEGMENT_LANDMARKS:
        idxs = [LANDMARK_INDEX[name] for name in SEGMENT_LANDMARKS[point] if name in LANDMARK_INDEX]
        pts = pose.xyz[frame_idx, idxs]
        mask = np.isfinite(pts).all(axis=1)
        if np.any(mask):
            return np.nanmean(pts[mask], axis=0)
    if point == "pelvis_center":
        pts = pose.xyz[frame_idx, [LANDMARK_INDEX["left_hip"], LANDMARK_INDEX["right_hip"]]]
        return np.nanmean(pts, axis=0)
    if point == "mid_feet":
        pts = pose.xyz[frame_idx, [LANDMARK_INDEX["left_ankle"], LANDMARK_INDEX["right_ankle"]]]
        return np.nanmean(pts, axis=0)
    raise KeyError(f"Unknown point alias '{point}'.")


def _point_from_provider(provider: PointLike | None, pose: PoseSequence3D, trial, frame_idx: int, time_s: float) -> np.ndarray:
    if provider is None:
        return np.zeros(3, dtype=float)
    if isinstance(provider, str):
        return _resolve_semantic_point(provider, pose, frame_idx)
    return _vector_from_provider(provider, trial, frame_idx, time_s)


def build(trial, *, global_pose, force_set: ForceSet | list[ExternalForce], segment_map: Mapping[str, str] | None = None) -> ForceSetResult:
    trial = ensure_trial(trial)
    pose: PoseSequence3D = global_pose.sequence if hasattr(global_pose, "sequence") else global_pose
    forces = force_set.forces if isinstance(force_set, ForceSet) else list(force_set)
    segment_map_resolved = {**DEFAULT_SEGMENT_MAP, **(dict(segment_map or {}))}
    rows: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    resolved_specs: list[ExternalForceSpec] = []

    force_arrays: dict[str, np.ndarray] = {}
    point_arrays: dict[str, np.ndarray] = {}
    torque_arrays: dict[str, np.ndarray] = {}

    for spec in forces:
        body = spec.applied_to_body or segment_map_resolved.get(spec.target, spec.target)
        mapping_rows.append(
            {
                "force_name": spec.name,
                "target": spec.target,
                "applied_to_body": body,
                "point_source": spec.point if isinstance(spec.point, str) else "(numeric/callable)",
            }
        )
        force_vectors = []
        point_vectors = []
        torque_vectors = []
        for frame_idx, t in enumerate(pose.time_s):
            active = ((spec.start_time is None or t >= spec.start_time) and (spec.end_time is None or t <= spec.end_time))
            if spec.force is not None:
                vec = _vector_from_provider(spec.force, trial, frame_idx, float(t))
            elif spec.magnitude is not None and spec.direction is not None:
                vec = float(spec.magnitude) * _normalize_vector(np.asarray(spec.direction, dtype=float))
            else:
                vec = np.zeros(3, dtype=float)
            point_vec = _point_from_provider(spec.point, pose, trial, frame_idx, float(t))
            torque_vec = _vector_from_provider(spec.torque, trial, frame_idx, float(t)) if spec.torque is not None else np.zeros(3, dtype=float)
            if not active:
                vec = np.zeros(3, dtype=float)
                torque_vec = np.zeros(3, dtype=float)
            force_vectors.append(vec)
            point_vectors.append(point_vec)
            torque_vectors.append(torque_vec)
            rows.append(
                {
                    "frame": frame_idx,
                    "time": float(t),
                    "force_name": spec.name,
                    "target": spec.target,
                    "applied_to_body": body,
                    "fx": float(vec[0]),
                    "fy": float(vec[1]),
                    "fz": float(vec[2]),
                    "px": float(point_vec[0]),
                    "py": float(point_vec[1]),
                    "pz": float(point_vec[2]),
                    "tx": float(torque_vec[0]),
                    "ty": float(torque_vec[1]),
                    "tz": float(torque_vec[2]),
                    "magnitude": float(np.linalg.norm(vec)),
                }
            )
        force_arrays[spec.name] = np.asarray(force_vectors, dtype=float)
        point_arrays[spec.name] = np.asarray(point_vectors, dtype=float)
        torque_arrays[spec.name] = np.asarray(torque_vectors, dtype=float)
        resolved_specs.append(
            ExternalForceSpec(
                name=spec.name,
                applied_to_body=body,
                force=force_arrays[spec.name],
                point=point_arrays[spec.name],
                torque=torque_arrays[spec.name],
                force_expressed_in_body=spec.reference_frame,
                point_expressed_in_body=spec.point_expressed_in_body,
            )
        )

    long_df = pd.DataFrame(rows)
    wide_df = long_df.pivot(index=["frame", "time"], columns="force_name", values=["fx", "fy", "fz", "px", "py", "pz", "tx", "ty", "tz", "magnitude"])
    if isinstance(wide_df.columns, pd.MultiIndex):
        wide_df.columns = [f"{name}_{axis}" for axis, name in wide_df.columns]
    wide_df = wide_df.reset_index() if not wide_df.empty else pd.DataFrame()
    mapping_df = pd.DataFrame(mapping_rows)
    if long_df.empty:
        summary_df = pd.DataFrame(columns=["force_name", "target", "applied_to_body", "max_force_magnitude", "active_frames", "mean_force_magnitude"])
    else:
        summary_df = (
            long_df.groupby(["force_name", "target", "applied_to_body"], as_index=False)
            .agg(
                max_force_magnitude=("magnitude", "max"),
                mean_force_magnitude=("magnitude", "mean"),
                active_frames=("magnitude", lambda s: int((s > 0).sum())),
            )
        )

    result = ForceSetResult(
        stage="forces",
        df=long_df,
        tables={
            "forces_long": long_df,
            "forces_wide": wide_df,
            "mapping": mapping_df,
            "summary": summary_df,
        },
        specs=forces,
        resolved_specs=resolved_specs,
        meta=stage_metadata(trial, depends_on=["global_pose"]),
    )
    return trial.register_stage("forces", result)
