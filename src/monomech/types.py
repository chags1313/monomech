"""Core dataclasses for pose and trial results."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .constants import LANDMARK_NAMES

VectorProvider = tuple[float, float, float] | list[float] | np.ndarray | Callable[["TrialResult", int, float], tuple[float, float, float]]


@dataclass(slots=True)
class PoseSequence2D:
    time_s: np.ndarray
    xy: np.ndarray
    visibility: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.time_s = np.asarray(self.time_s, dtype=float)
        self.xy = np.asarray(self.xy, dtype=float)
        self.visibility = np.asarray(self.visibility, dtype=float)

    @property
    def n_frames(self) -> int:
        return int(self.xy.shape[0])

    @property
    def n_landmarks(self) -> int:
        return int(self.xy.shape[1])

    def to_dataframe(self) -> pd.DataFrame:
        rows: dict[str, Any] = {"time": self.time_s}
        for idx, name in enumerate(LANDMARK_NAMES[: self.n_landmarks]):
            rows[f"{name}_x"] = self.xy[:, idx, 0]
            rows[f"{name}_y"] = self.xy[:, idx, 1]
            rows[f"{name}_visibility"] = self.visibility[:, idx]
        return pd.DataFrame(rows)


@dataclass(slots=True)
class PoseSequence3D:
    time_s: np.ndarray
    xyz: np.ndarray
    visibility: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.time_s = np.asarray(self.time_s, dtype=float)
        self.xyz = np.asarray(self.xyz, dtype=float)
        self.visibility = np.asarray(self.visibility, dtype=float)

    @property
    def n_frames(self) -> int:
        return int(self.xyz.shape[0])

    @property
    def n_landmarks(self) -> int:
        return int(self.xyz.shape[1])

    def copy(self) -> "PoseSequence3D":
        return PoseSequence3D(
            time_s=self.time_s.copy(),
            xyz=self.xyz.copy(),
            visibility=self.visibility.copy(),
            metadata=dict(self.metadata),
        )

    def to_dataframe(self) -> pd.DataFrame:
        rows: dict[str, Any] = {"time": self.time_s}
        for idx, name in enumerate(LANDMARK_NAMES[: self.n_landmarks]):
            rows[f"{name}_x"] = self.xyz[:, idx, 0]
            rows[f"{name}_y"] = self.xyz[:, idx, 1]
            rows[f"{name}_z"] = self.xyz[:, idx, 2]
            rows[f"{name}_visibility"] = self.visibility[:, idx]
        return pd.DataFrame(rows)


@dataclass(slots=True)
class ExternalForceSpec:
    name: str
    applied_to_body: str
    force: VectorProvider
    point: VectorProvider
    torque: VectorProvider | None = None
    force_expressed_in_body: str = "ground"
    point_expressed_in_body: str = "ground"
    force_identifier: str | None = None
    point_identifier: str | None = None
    torque_identifier: str | None = None


@dataclass(slots=True)
class TrialResult:
    name: str
    video_path: Path | None
    fps: float
    pose2d: PoseSequence2D | None = None
    world_pose: PoseSequence3D | None = None
    pnp_pose: PoseSequence3D | None = None
    global_pose: PoseSequence3D | None = None
    artifacts: dict[str, Path] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_pose(self, coordinate_set: str = "global") -> PoseSequence3D:
        mapping = {
            "global": self.global_pose,
            "pnp": self.pnp_pose,
            "world": self.world_pose,
        }
        pose = mapping.get(coordinate_set)
        if pose is None:
            available = [key for key, value in mapping.items() if value is not None]
            raise KeyError(f"Pose '{coordinate_set}' is unavailable. Available: {available}")
        return pose

    def add_artifact(self, name: str, path: str | Path) -> Path:
        resolved = Path(path)
        self.artifacts[name] = resolved
        return resolved

    def export_dashboard_html(self, output_path: str | Path, coordinate_set: str = "global") -> Path:
        from .visualization.dashboard import export_trial_dashboard_html

        path = export_trial_dashboard_html(self, output_path=output_path, coordinate_set=coordinate_set)
        self.artifacts["dashboard_html"] = path
        return path

    def export_csv_bundle(self, output_dir: str | Path) -> dict[str, Path]:
        from .io.tabular import export_trial_csv_bundle

        return export_trial_csv_bundle(self, output_dir)

    def export_trc(self, output_path: str | Path, coordinate_set: str = "global") -> Path:
        from .io.opensim import write_trc_from_trial

        path = write_trc_from_trial(self, output_path=output_path, coordinate_set=coordinate_set)
        self.artifacts[f"{coordinate_set}_trc"] = path
        return path
