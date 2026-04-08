from __future__ import annotations

import io
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import GapFillConfig
from .filters import apply_smoothing, gap_fill_array
from .landmarks import FOOT_MARKERS, NAME_TO_INDEX
from .qc import QCReport


@dataclass(slots=True)
class BaseResult:
    name: str
    data: np.ndarray
    time: np.ndarray
    landmark_names: list[str]
    dims: tuple[str, ...]
    confidence: np.ndarray | None = None
    metadata: dict[str, Any] | None = None
    source: str = "unknown"
    fps: float | None = None

    @property
    def array(self) -> np.ndarray:
        return self.data

    @property
    def landmarks(self) -> list[str]:
        return self.landmark_names

    @property
    def frames(self) -> int:
        return int(self.data.shape[0])

    def copy(self):
        return replace(
            self,
            data=self.data.copy(),
            time=self.time.copy(),
            confidence=None if self.confidence is None else self.confidence.copy(),
            metadata=dict(self.metadata or {}),
        )

    def to_wide_df(self) -> pd.DataFrame:
        rows: dict[str, np.ndarray] = {"frame": np.arange(self.frames, dtype=int), "time_s": self.time}
        for m, landmark in enumerate(self.landmark_names):
            for d, dim in enumerate(self.dims):
                rows[f"{landmark}_{dim}"] = self.data[:, m, d]
            if self.confidence is not None:
                rows[f"{landmark}_confidence"] = self.confidence[:, m]
        return pd.DataFrame(rows)

    def to_long_df(self) -> pd.DataFrame:
        frames = self.to_wide_df()
        value_cols = [c for c in frames.columns if c not in {"frame", "time_s"}]
        return frames.melt(id_vars=["frame", "time_s"], value_vars=value_cols, var_name="channel", value_name="value")

    def to_csv(self, path: str | Path, *, format: str = "wide") -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df = self.to_wide_df() if format == "wide" else self.to_long_df()
        df.to_csv(path, index=False)
        return path

    def threshold_confidence(self, min_confidence: float = 0.35, mode: str = "set_missing"):
        if self.confidence is None:
            return self.copy()
        out = self.copy()
        mask = out.confidence < min_confidence
        if mode == "set_missing":
            for d in range(out.data.shape[2]):
                out.data[:, :, d][mask] = np.nan
        out.metadata = dict(out.metadata or {})
        out.metadata["confidence_threshold"] = min_confidence
        return out

    def gap_fill(
        self,
        *,
        method: str = "pchip",
        max_gap_frames: int = 10,
        fill_edges: bool = False,
        inplace: bool = False,
    ):
        target = self if inplace else self.copy()
        target.data = gap_fill_array(
            target.data,
            method=method,
            max_gap_frames=max_gap_frames,
            fill_edges=fill_edges,
        )
        target.metadata = dict(target.metadata or {})
        target.metadata["gap_fill"] = {
            "method": method,
            "max_gap_frames": max_gap_frames,
            "fill_edges": fill_edges,
        }
        return target

    def smooth(
        self,
        *,
        method: str = "butterworth",
        fps: float | None = None,
        cutoff_hz: float = 6.0,
        order: int = 4,
        window_length: int = 11,
        polyorder: int = 3,
        preserve_segment_lengths: bool = False,
        inplace: bool = False,
    ):
        target = self if inplace else self.copy()
        target.data = apply_smoothing(
            target.data,
            method=method,
            fps=float(fps or self.fps or 30.0),
            confidence=target.confidence,
            cutoff_hz=cutoff_hz,
            order=order,
            window_length=window_length,
            polyorder=polyorder,
            preserve_lengths=preserve_segment_lengths,
            landmark_names=target.landmark_names,
        )
        target.metadata = dict(target.metadata or {})
        target.metadata["smoothing"] = {
            "method": method,
            "cutoff_hz": cutoff_hz,
            "order": order,
            "window_length": window_length,
            "polyorder": polyorder,
            "preserve_segment_lengths": preserve_segment_lengths,
        }
        return target

    def clean(
        self,
        *,
        min_confidence: float | None = 0.35,
        gap_fill_method: str = "pchip",
        gap_fill_max_frames: int = 10,
        smooth_method: str = "butterworth",
        cutoff_hz: float = 6.0,
        preserve_segment_lengths: bool = False,
    ):
        result = self
        if min_confidence is not None:
            result = result.threshold_confidence(min_confidence=min_confidence)
        result = result.gap_fill(method=gap_fill_method, max_gap_frames=gap_fill_max_frames)
        result = result.smooth(
            method=smooth_method,
            cutoff_hz=cutoff_hz,
            preserve_segment_lengths=preserve_segment_lengths,
        )
        return result

    def summary(self) -> pd.DataFrame:
        rows = []
        for i, name in enumerate(self.landmark_names):
            valid = np.isfinite(self.data[:, i, :]).all(axis=1)
            conf = None if self.confidence is None else self.confidence[:, i]
            rows.append(
                {
                    "landmark": name,
                    "valid_frames": int(valid.sum()),
                    "missing_frames": int((~valid).sum()),
                    "missing_pct": float((~valid).mean() * 100.0),
                    "mean_confidence": None if conf is None else float(np.nanmean(conf)),
                }
            )
        return pd.DataFrame(rows)

    def qc_report(self) -> QCReport:
        return QCReport(self.summary())

    def _plot(self, series: dict[str, np.ndarray], title: str):
        try:
            import matplotlib.pyplot as plt
        except Exception as exc:
            raise ImportError("matplotlib is required for plotting. Install monomech[notebook].") from exc
        fig, ax = plt.subplots(figsize=(10, 4))
        for label, values in series.items():
            ax.plot(self.time, values, label=label)
        ax.set_title(title)
        ax.set_xlabel("Time (s)")
        ax.legend()
        plt.tight_layout()
        return ax

    def plot_landmark(self, landmark: str):
        idx = self.landmark_names.index(landmark)
        return self._plot(
            {f"{landmark}_{dim}": self.data[:, idx, d] for d, dim in enumerate(self.dims)},
            title=f"{self.name}: {landmark}",
        )


@dataclass(slots=True)
class Pose2DResult(BaseResult):
    dims: tuple[str, ...] = ("x_norm", "y_norm")


@dataclass(slots=True)
class Pose3DWorldResult(BaseResult):
    dims: tuple[str, ...] = ("x_m", "y_m", "z_m")

    def preview_3d(self):
        return self.plot_landmark("right_ankle" if "right_ankle" in self.landmark_names else self.landmark_names[0])


@dataclass(slots=True)
class Pose3DGlobalResult(Pose3DWorldResult):
    def plot_xyz(self, landmark: str):
        return self.plot_landmark(landmark)

    def to_trc(
        self,
        path: str | Path,
        *,
        model_path: str | Path | None = None,
        marker_set: list[str] | None = None,
        marker_map: dict[str, str] | None = None,
        units: str = "m",
        axis_map: dict[str, tuple[int, float]] | None = None,
        ground_y: bool = True,
    ) -> Path:
        data = self.data.copy()
        names = self.landmark_names[:]
        if marker_set is not None:
            keep = [names.index(name) for name in marker_set if name in names]
            names = [names[i] for i in keep]
            data = data[:, keep, :]
        if marker_map:
            keep = [names.index(src) for src in marker_map.keys() if src in names]
            names = [marker_map[names[i]] for i in keep]
            data = data[:, keep, :]
        if axis_map is None:
            # OpenSim-friendly default copied from the prototype logic:
            # X = z, Y = y, Z = x
            remapped = np.empty_like(data)
            remapped[:, :, 0] = data[:, :, 2]
            remapped[:, :, 1] = data[:, :, 1]
            remapped[:, :, 2] = data[:, :, 0]
            data = remapped
        else:
            remapped = np.empty_like(data)
            for out_idx, key in enumerate(("x", "y", "z")):
                src_idx, sign = axis_map[key]
                remapped[:, :, out_idx] = data[:, :, src_idx] * sign
            data = remapped
        if ground_y:
            y_min = np.nanmin(data[:, :, 1])
            if np.isfinite(y_min):
                data[:, :, 1] -= y_min
        from .io.trc import write_trc
        return write_trc(path, time=self.time, data=data, marker_names=names, units=units, fps=self.fps)


@dataclass(slots=True)
class MarkerResult(Pose3DGlobalResult):
    def to_trc(
        self,
        path: str | Path,
        *,
        model_path: str | Path | None = None,
        marker_set: list[str] | None = None,
        marker_map: dict[str, str] | None = None,
        units: str = "m",
        axis_map: dict[str, tuple[int, float]] | None = None,
        ground_y: bool = False,
    ) -> Path:
        data = self.data.copy()
        names = self.landmark_names[:]
        if marker_set is not None:
            keep = [names.index(name) for name in marker_set if name in names]
            names = [names[i] for i in keep]
            data = data[:, keep, :]
        if marker_map:
            keep = [names.index(src) for src in marker_map.keys() if src in names]
            names = [marker_map[names[i]] for i in keep]
            data = data[:, keep, :]
        if axis_map is not None:
            remapped = np.empty_like(data)
            for out_idx, key in enumerate(("x", "y", "z")):
                src_idx, sign = axis_map[key]
                remapped[:, :, out_idx] = data[:, :, src_idx] * sign
            data = remapped
        from .io.trc import write_trc
        return write_trc(path, time=self.time, data=data, marker_names=names, units=units, fps=self.fps)


@dataclass(slots=True)
class StorageResult:
    path: Path
    dataframe: pd.DataFrame
    metadata: dict[str, Any] | None = None

    def to_dataframe(self) -> pd.DataFrame:
        return self.dataframe.copy()

    @property
    def motion_path(self) -> Path:
        return self.path

    def summary(self) -> pd.DataFrame:
        return self.dataframe.describe().T


@dataclass(slots=True)
class OpenSimScaleResult:
    scaled_model_path: Path
    setup_xml_path: Path | None = None
    log_path: Path | None = None
    metadata: dict[str, Any] | None = None

    def summary(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "scaled_model_path": str(self.scaled_model_path),
                    "setup_xml_path": None if self.setup_xml_path is None else str(self.setup_xml_path),
                    "log_path": None if self.log_path is None else str(self.log_path),
                }
            ]
        )


@dataclass(slots=True)
class PipelineRun:
    pose2d: Pose2DResult | None = None
    pose3d_world: Pose3DWorldResult | None = None
    pose3d_global: Pose3DGlobalResult | None = None
    trc_path: Path | None = None
    csv_paths: list[Path] | None = None
