from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(slots=True)
class ExternalLoadsSpec:
    name: str
    data: pd.DataFrame
    force_expressed_in: str
    point_expressed_in: str
    applied_to_body: str
    force_columns: tuple[str, str, str]
    point_columns: tuple[str, str, str]
    torque_columns: tuple[str, str, str] | None = None
    time_column: str = "time"
    units: str = "N"
    point_units: str = "m"
    source: str = "manual"
    is_estimated: bool = False
    metadata: dict | None = None

    def to_dataframe(self) -> pd.DataFrame:
        return self.data.copy()


class _ExternalFactory:
    def from_dataframe(
        self,
        *,
        df: pd.DataFrame,
        applied_to_body: str,
        force_columns: tuple[str, str, str],
        point_columns: tuple[str, str, str],
        torque_columns: tuple[str, str, str] | None = None,
        time_column: str = "time",
        units: str = "N",
        point_units: str = "m",
        name: str = "external_load",
        force_expressed_in: str = "/ground",
        point_expressed_in: str = "/ground",
    ) -> ExternalLoadsSpec:
        return ExternalLoadsSpec(
            name=name,
            data=df.copy(),
            force_expressed_in=force_expressed_in,
            point_expressed_in=point_expressed_in,
            applied_to_body=applied_to_body,
            force_columns=force_columns,
            point_columns=point_columns,
            torque_columns=torque_columns,
            time_column=time_column,
            units=units,
            point_units=point_units,
            source="dataframe",
            is_estimated=False,
        )

    def from_csv(self, path: str | Path, **kwargs) -> ExternalLoadsSpec:
        path = Path(path)
        return self.from_dataframe(df=pd.read_csv(path), **kwargs)

    def from_timeseries(
        self,
        *,
        time: np.ndarray,
        force: np.ndarray,
        point: np.ndarray,
        applied_to_body: str,
        torque: np.ndarray | None = None,
        name: str = "timeseries_load",
        force_expressed_in: str = "/ground",
        point_expressed_in: str = "/ground",
    ) -> ExternalLoadsSpec:
        time = np.asarray(time, dtype=float)
        force = np.asarray(force, dtype=float)
        point = np.asarray(point, dtype=float)

        if force.ndim != 2 or force.shape[1] != 3:
            raise ValueError("force must have shape (n, 3)")
        if point.ndim != 2 or point.shape[1] != 3:
            raise ValueError("point must have shape (n, 3)")
        if len(time) != len(force) or len(time) != len(point):
            raise ValueError("time, force, and point must have the same length")

        df = pd.DataFrame({"time": time})
        force_cols = ("Fx", "Fy", "Fz")
        point_cols = ("Px", "Py", "Pz")

        for i, col in enumerate(force_cols):
            df[col] = force[:, i]
        for i, col in enumerate(point_cols):
            df[col] = point[:, i]

        torque_cols = None
        if torque is not None:
            torque = np.asarray(torque, dtype=float)
            if torque.ndim != 2 or torque.shape[1] != 3 or len(torque) != len(time):
                raise ValueError("torque must have shape (n, 3) and match time length")
            torque_cols = ("Mx", "My", "Mz")
            for i, col in enumerate(torque_cols):
                df[col] = torque[:, i]

        return self.from_dataframe(
            df=df,
            applied_to_body=applied_to_body,
            force_columns=force_cols,
            point_columns=point_cols,
            torque_columns=torque_cols,
            time_column="time",
            name=name,
            force_expressed_in=force_expressed_in,
            point_expressed_in=point_expressed_in,
        )

    @staticmethod
    def constant_force(
        *,
        applied_to_body: str,
        force: tuple[float, float, float],
        point: tuple[float, float, float] = (0.0, 0.0, 0.0),
        start_time: float,
        end_time: float,
        name: str = "manual_load",
        force_expressed_in: str = "/ground",
        point_expressed_in: str | None = None,
    ) -> ExternalLoadsSpec:
        if point_expressed_in is None:
            point_expressed_in = applied_to_body

        if not end_time > start_time:
            raise ValueError("end_time must be greater than start_time")

        df = pd.DataFrame(
            {
                "time": [float(start_time), float(end_time)],
                "Fx": [float(force[0]), float(force[0])],
                "Fy": [float(force[1]), float(force[1])],
                "Fz": [float(force[2]), float(force[2])],
                "Px": [float(point[0]), float(point[0])],
                "Py": [float(point[1]), float(point[1])],
                "Pz": [float(point[2]), float(point[2])],
                "Tx": [0.0, 0.0],
                "Ty": [0.0, 0.0],
                "Tz": [0.0, 0.0],
            }
        )

        return ExternalLoadsSpec(
            name=name,
            data=df,
            force_expressed_in=force_expressed_in,
            point_expressed_in=point_expressed_in,
            applied_to_body=applied_to_body,
            force_columns=("Fx", "Fy", "Fz"),
            point_columns=("Px", "Py", "Pz"),
            torque_columns=("Tx", "Ty", "Tz"),
            time_column="time",
            units="N",
            point_units="m",
            source="manual",
            is_estimated=False,
            metadata={
                "start_time": float(start_time),
                "end_time": float(end_time),
            },
        )

    def carried_load(
        self,
        *,
        body: str,
        mass_kg: float,
        direction: str = "global_down",
        start_time: float = 0.0,
        end_time: float = 1.0,
        name: str = "carried_load",
    ) -> ExternalLoadsSpec:
        g = 9.81
        if direction != "global_down":
            raise ValueError("Only direction='global_down' is supported in this scaffold.")

        return self.constant_force(
            applied_to_body=body,
            force=(0.0, -mass_kg * g, 0.0),
            point=(0.0, 0.0, 0.0),
            start_time=start_time,
            end_time=end_time,
            name=name,
            force_expressed_in="/ground",
            point_expressed_in=body,
        )

    def estimate_grf(
        self,
        *,
        pose3d,
        method: str = "contact_vertical",
        sides: tuple[str, ...] = ("left", "right"),
        body_mass_kg: float = 75.0,
        name: str = "estimated_grf",
        opensim_axes: bool = True,
        ground_y: bool = True,
    ) -> list[ExternalLoadsSpec]:
        time = np.asarray(pose3d.time, dtype=float)
        g = 9.81

        landmark_names = getattr(pose3d, "landmark_names", None)
        if landmark_names is None:
            landmark_names = getattr(pose3d, "landmarks", None)
        if landmark_names is None:
            raise ValueError("pose3d must provide landmark_names or landmarks")

        data = getattr(pose3d, "data", None)
        if data is None:
            data = getattr(pose3d, "array", None)
        if data is None:
            raise ValueError("pose3d must provide data or array")

        data = np.asarray(data, dtype=float)
        if opensim_axes:
            remapped = np.empty_like(data)
            remapped[:, :, 0] = data[:, :, 2]
            remapped[:, :, 1] = data[:, :, 1]
            remapped[:, :, 2] = data[:, :, 0]
            data = remapped
        if ground_y and data.shape[2] >= 2:
            floor = np.nanmin(data[:, :, 1])
            if np.isfinite(floor):
                data[:, :, 1] -= floor

        foot_map = {
            "left": ["left_heel", "left_foot_index", "left_ankle"],
            "right": ["right_heel", "right_foot_index", "right_ankle"],
        }

        side_points: dict[str, np.ndarray] = {}
        side_heights: dict[str, np.ndarray] = {}
        loads: list[ExternalLoadsSpec] = []

        for side in sides:
            markers = [m for m in foot_map[side] if m in landmark_names]
            if not markers:
                continue

            idx = [landmark_names.index(m) for m in markers]
            side_points[side] = np.nanmean(data[:, idx, :3], axis=1)
            side_heights[side] = np.nanmean(data[:, idx, 1], axis=1)

        if not side_points:
            return loads

        finite_heights = np.concatenate(
            [height[np.isfinite(height)] for height in side_heights.values()]
        )
        floor_height = float(np.nanpercentile(finite_heights, 5)) if finite_heights.size else 0.0
        height_scale = 0.08
        weights = {}
        for side, height in side_heights.items():
            height_above_floor = np.clip(height - floor_height, 0.0, None)
            weight = np.exp(-height_above_floor / height_scale)
            weight[~np.isfinite(weight)] = 0.0
            weights[side] = weight

        total_weight = np.sum(np.vstack(list(weights.values())), axis=0)
        valid_support = total_weight > 1e-9

        for side, point in side_points.items():
            support = np.zeros_like(time, dtype=float)
            support[valid_support] = (
                weights[side][valid_support] / total_weight[valid_support] * body_mass_kg * g
            )
            if not np.all(valid_support):
                support[~valid_support] = body_mass_kg * g / max(1, len(side_points))
            force = np.column_stack([np.zeros_like(support), support, np.zeros_like(support)])

            spec = self.from_timeseries(
                time=time,
                force=force,
                point=point,
                applied_to_body=f"calcn_{'l' if side == 'left' else 'r'}",
                name=f"{name}_{side}",
                force_expressed_in="/ground",
                point_expressed_in="/ground",
            )
            spec.is_estimated = True
            spec.source = method
            spec.metadata = {
                "method": method,
                "body_mass_kg": float(body_mass_kg),
                "floor_height": floor_height,
                "height_scale_m": height_scale,
                "opensim_axes": bool(opensim_axes),
                "ground_y": bool(ground_y),
                "note": (
                    "Estimated GRF is a visualization and inverse-dynamics fallback, "
                    "not measured force-plate data."
                ),
            }
            loads.append(spec)

        return loads


external = _ExternalFactory()
