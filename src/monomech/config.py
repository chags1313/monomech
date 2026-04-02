"""Configuration dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class MediaPipePoseConfig:
    model_asset_path: str | None = None
    model_variant: str = "heavy"
    target_fps: float | None = 60.0
    stride: int = 1
    num_poses: int = 1
    min_pose_detection_confidence: float = 0.5
    min_pose_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    output_segmentation_masks: bool = False
    allow_model_download: bool = True
    model_cache_dir: str | None = None


@dataclass(slots=True)
class PnPConfig:
    enabled: bool = True
    focal_length_factor: float = 0.60
    min_points: int = 6
    max_points: int = 12
    min_visibility: float = 0.18
    ransac: bool = True
    reprojection_error_px: float = 8.0
    confidence: float = 0.99
    iterations_count: int = 120


@dataclass(slots=True)
class GlobalPoseConfig:
    enabled: bool = True
    contact_height_m: float = 0.06
    contact_release_height_m: float = 0.10
    contact_speed_m_s: float = 0.40
    smoothing_window: int = 5
    floor_quantile: float = 0.1


@dataclass(slots=True)
class OpenSimConfig:
    model_path: str | None = None
    model_preset: str | None = "auto"
    output_dirname: str = "opensim"
    run_scale: bool = False
    run_ik: bool = True
    run_id: bool = False
    export_marker_trc: bool = True
    export_landmark_trc: bool = True
    marker_export_set: str = "model_or_preset"
    coordinate_set: str = "global"
    scale_time_window: tuple[float, float] | None = None
    scale_window_mode: str = "auto"
    scale_window_seconds: float = 1.0
    scale_min_frames: int = 10
    ik_marker_weight: float = 1.0
    scale_marker_weight: float = 1.0
    id_lowpass_cutoff: float = -1.0
    use_subprocess: bool = True
    keep_setup_xml: bool = True
    write_csv_copies: bool = True


@dataclass(slots=True)
class DashboardConfig:
    coordinate_set: str = "global"
    joint_for_trace: str = "right_ankle"
    include_plotlyjs: str | bool = "inline"
    title: str = "monomech trial dashboard"


@dataclass(slots=True)
class PipelineConfig:
    pose: MediaPipePoseConfig = field(default_factory=MediaPipePoseConfig)
    pnp: PnPConfig = field(default_factory=PnPConfig)
    global_pose: GlobalPoseConfig = field(default_factory=GlobalPoseConfig)
    opensim: OpenSimConfig = field(default_factory=OpenSimConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_output_dir(self, output_dir: str | Path) -> "PipelineConfig":
        copied = PipelineConfig(
            pose=self.pose,
            pnp=self.pnp,
            global_pose=self.global_pose,
            opensim=self.opensim,
            dashboard=self.dashboard,
            metadata={**self.metadata, "output_dir": str(output_dir)},
        )
        return copied
