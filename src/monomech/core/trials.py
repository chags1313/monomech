from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import (
    OpenSimIDConfig,
    OpenSimIKConfig,
    OpenSimScaleConfig,
    Pose2DConfig,
    Pose3DGlobalConfig,
    Pose3DWorldConfig,
)
from ..opensim_api import run_id, run_ik, run_scale
from ..pose import estimate_global_pose, estimate_pose_from_video
from ..results import MarkerResult, PipelineRun, Pose2DResult, Pose3DGlobalResult, Pose3DWorldResult
from ..utils import ensure_dir
from ..io.trc import load_trc


@dataclass(slots=True)
class BaseTrial:
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source_path: str | Path | None = None

    def run_opensim_scale(
        self,
        *,
        model_path: str | Path,
        trc_path: str | Path | None = None,
        output_dir: str | Path | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        config: OpenSimScaleConfig | None = None,
    ):
        trc = Path(trc_path) if trc_path is not None else self.last_trc_path
        if trc is None:
            raise ValueError("No TRC path provided and no default TRC is available on this trial.")

        output_dir = output_dir or Path("outputs") / self.name / "scale"

        config = config or OpenSimScaleConfig()

        if start_time is not None or end_time is not None:
            marker_trial = load_trc(trc)
            time = marker_trial.markers.time
            if time is None or len(time) < 2:
                raise ValueError(f"TRC file must contain at least 2 valid time samples: {trc}")

            t0 = float(time[0]) if start_time is None else float(start_time)
            t1 = float(time[-1]) if end_time is None else float(end_time)

            if not t1 > t0:
                raise ValueError(f"Invalid scale time range: start_time={t0}, end_time={t1}")

            config.time_window = (t0, t1)

        return run_scale(
            trc_path=trc,
            model_path=model_path,
            output_dir=output_dir,
            config=config,
        )

    def run_opensim_ik(
        self,
        *,
        model_path: str | Path,
        trc_path: str | Path | None = None,
        output_dir: str | Path | None = None,
        config: OpenSimIKConfig | None = None,
    ):
        trc = Path(trc_path) if trc_path is not None else self._default_trc_path()
        if trc is None:
            raise ValueError("No TRC path provided and no default TRC is available on this trial.")
        output_dir = output_dir or Path("outputs") / self.name / "ik"
        return run_ik(trc_path=trc, model_path=model_path, output_dir=output_dir, config=config)

    def run_opensim_id(
        self,
        *,
        model_path: str | Path,
        ik_path: str | Path,
        external_forces=None,
        output_dir: str | Path | None = None,
        config: OpenSimIDConfig | None = None,
    ):
        output_dir = output_dir or Path("outputs") / self.name / "id"
        return run_id(
            ik_path=ik_path,
            model_path=model_path,
            output_dir=output_dir,
            external_forces=external_forces,
            config=config,
        )

    def _default_trc_path(self) -> Path | None:
        return None


@dataclass(slots=True)
class VideoTrial(BaseTrial):
    video_path: Path | None = None
    pose2d_result: Pose2DResult | None = None
    pose3d_world_result: Pose3DWorldResult | None = None
    pose3d_global_result: Pose3DGlobalResult | None = None
    last_trc_path: Path | None = None

    @property
    def pose2d(self):
        return self.pose2d_result

    @property
    def pose3d_world(self):
        return self.pose3d_world_result

    @property
    def pose3d_global(self):
        return self.pose3d_global_result

    def estimate_pose2d(
        self,
        *,
        backend: str = "mediapipe",
        fps: float | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        stride: int = 1,
        smooth: bool = True,
        config: Pose2DConfig | None = None,
    ) -> Pose2DResult:
        if self.video_path is None:
            raise ValueError("This VideoTrial does not have a video_path.")
        cfg = config or Pose2DConfig(backend=backend, stride=stride, sample_fps=fps, smooth_landmarks=smooth)
        pose2d, pose3d_world = estimate_pose_from_video(self.video_path, config=cfg)
        self.pose2d_result = pose2d
        self.pose3d_world_result = pose3d_world
        return pose2d

    def estimate_pose3d_world(
        self,
        *,
        source: str = "video",
        backend: str = "mediapipe",
        smooth: bool = True,
        config: Pose3DWorldConfig | None = None,
    ) -> Pose3DWorldResult:
        if self.pose3d_world_result is None:
            self.estimate_pose2d(backend=backend, smooth=smooth)
        assert self.pose3d_world_result is not None
        if smooth:
            self.pose3d_world_result = self.pose3d_world_result.smooth(method="butterworth", cutoff_hz=6.0)
        return self.pose3d_world_result

    def estimate_pose3d_global(
        self,
        *,
        world_pose: Pose3DWorldResult | None = None,
        pose2d: Pose2DResult | None = None,
        floor_method: str = "auto",
        translation_method: str = "pnp",
        smooth_root: bool = True,
        config: Pose3DGlobalConfig | None = None,
    ) -> Pose3DGlobalResult:
        world_pose = world_pose or self.pose3d_world_result or self.estimate_pose3d_world()
        pose2d = pose2d or self.pose2d_result
        cfg = config or Pose3DGlobalConfig(
            floor_method=floor_method,
            translation_method=translation_method,
            smooth_root=smooth_root,
        )
        self.pose3d_global_result = estimate_global_pose(world_pose, pose2d, config=cfg)
        return self.pose3d_global_result

    def export_csvs(self, *, output_dir: str | Path, include: tuple[str, ...] = ("pose2d", "pose3d_world", "pose3d_global")) -> list[Path]:
        out = ensure_dir(output_dir)
        paths: list[Path] = []
        mapping = {
            "pose2d": self.pose2d_result,
            "pose3d_world": self.pose3d_world_result,
            "pose3d_global": self.pose3d_global_result,
        }
        for key in include:
            result = mapping.get(key)
            if result is not None:
                paths.append(result.to_csv(out / f"{self.name}_{key}.csv"))
        return paths

    def run_pipeline(
        self,
        *,
        pose2d: bool = True,
        pose3d_world: bool = True,
        pose3d_global: bool = True,
        export_csv: bool = False,
        export_trc: bool = False,
        model_path: str | Path | None = None,
        output_dir: str | Path = "outputs",
    ) -> PipelineRun:
        out = ensure_dir(output_dir)
        run = PipelineRun()
        if pose2d:
            run.pose2d = self.estimate_pose2d()
        if pose3d_world:
            run.pose3d_world = self.estimate_pose3d_world()
        if pose3d_global:
            run.pose3d_global = self.estimate_pose3d_global()
        if export_csv:
            run.csv_paths = self.export_csvs(output_dir=out)
        if export_trc:
            if self.pose3d_global_result is None:
                self.estimate_pose3d_global()
            assert self.pose3d_global_result is not None
            trc_path = out / f"{self.name}.trc"
            self.last_trc_path = self.pose3d_global_result.to_trc(trc_path, model_path=model_path)
            run.trc_path = self.last_trc_path
        return run

    def save_package(self, path: str | Path, include: tuple[str, ...] = ("pose2d", "pose3d_world", "pose3d_global", "ik", "id")) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("metadata.json", json.dumps({"name": self.name, "metadata": self.metadata}, indent=2))
            if "pose2d" in include and self.pose2d_result is not None:
                zf.writestr("pose2d.csv", self.pose2d_result.to_wide_df().to_csv(index=False))
            if "pose3d_world" in include and self.pose3d_world_result is not None:
                zf.writestr("pose3d_world.csv", self.pose3d_world_result.to_wide_df().to_csv(index=False))
            if "pose3d_global" in include and self.pose3d_global_result is not None:
                zf.writestr("pose3d_global.csv", self.pose3d_global_result.to_wide_df().to_csv(index=False))
        return path

    def _default_trc_path(self) -> Path | None:
        return self.last_trc_path


@dataclass(slots=True)
class MarkerTrial(BaseTrial):
    markers: MarkerResult | None = None
    last_trc_path: Path | None = None

    @property
    def marker_names(self) -> list[str]:
        return [] if self.markers is None else self.markers.landmark_names

    @property
    def sampling_rate(self) -> float | None:
        return None if self.markers is None else self.markers.fps

    @property
    def time_range(self) -> tuple[float, float] | None:
        if self.markers is None or len(self.markers.time) == 0:
            return None
        return float(self.markers.time[0]), float(self.markers.time[-1])

    def summary(self) -> pd.DataFrame:
        if self.markers is None:
            return pd.DataFrame()
        return self.markers.summary()

    def validate_against_model(self, model_path: str | Path) -> pd.DataFrame:
        from ..io.model import inspect_model_markers
        if self.markers is None:
            return pd.DataFrame()
        model_markers = inspect_model_markers(model_path)["marker_name"].str.lower().tolist()
        rows = []
        for marker in self.markers.landmark_names:
            rows.append({"marker": marker, "in_model": marker.lower() in model_markers})
        return pd.DataFrame(rows)

    def build_marker_map(self, model_path: str | Path) -> dict[str, str]:
        from ..io.model import build_marker_map, inspect_model_markers
        if self.markers is None:
            return {}
        model_markers = inspect_model_markers(model_path)["marker_name"].tolist()
        return build_marker_map(self.markers.landmark_names, model_markers)

    def gap_fill(self, *, method: str = "rigid_cluster", max_gap_frames: int = 20):
        if self.markers is None:
            raise ValueError("No marker data loaded.")
        self.markers = self.markers.gap_fill(method=method, max_gap_frames=max_gap_frames)
        return self

    def smooth_markers(self, *, method: str = "butterworth", cutoff_hz: float = 6.0, order: int = 4):
        if self.markers is None:
            raise ValueError("No marker data loaded.")
        self.markers = self.markers.smooth(method=method, cutoff_hz=cutoff_hz, order=order)
        return self

    def clean_markers(
        self,
        *,
        gap_fill_method: str = "rigid_cluster",
        gap_fill_max_frames: int = 20,
        smooth_method: str = "butterworth",
        cutoff_hz: float = 6.0,
        order: int = 4,
    ):
        return self.gap_fill(method=gap_fill_method, max_gap_frames=gap_fill_max_frames).smooth_markers(
            method=smooth_method,
            cutoff_hz=cutoff_hz,
            order=order,
        )

    def to_trc(self, path: str | Path, *, units: str = "m") -> Path:
        if self.markers is None:
            raise ValueError("No marker data loaded.")
        self.last_trc_path = self.markers.to_trc(path, units=units)
        return self.last_trc_path

    def _default_trc_path(self) -> Path | None:
        return self.last_trc_path or (Path(self.source_path) if self.source_path else None)
