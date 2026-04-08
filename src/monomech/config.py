from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from pathlib import Path


@dataclass(slots=True)
class Pose2DConfig:
    backend: str = "mediapipe"
    model_complexity: int = 2
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    sample_fps: float | None = None
    stride: int = 1
    smooth_landmarks: bool = True
    # New for Tasks API
    pose_model_path: str | Path | None = None
    num_poses: int = 1


@dataclass(slots=True)
class Pose3DWorldConfig:
    backend: str = "mediapipe"
    smooth: bool = True


@dataclass(slots=True)
class Pose3DGlobalConfig:
    floor_method: Literal["auto", "feet_median", "min_y"] = "auto"
    translation_method: Literal["pnp", "hip_center"] = "pnp"
    pnp_min_points: int = 6
    focal_length_factor: float = 0.9
    smooth_root: bool = True
    root_smoothing_cutoff_hz: float = 4.0
    floor_percentile: float = 0.5
        # add these
    pnp_confidence_threshold: float = 0.2



@dataclass(slots=True)
class ButterworthConfig:
    cutoff_hz: float = 6.0
    order: int = 4
    zero_lag: bool = True


@dataclass(slots=True)
class GapFillConfig:
    method: Literal[
        "linear", "pchip", "cubic_spline", "nearest_valid", "rigid_segment", "rigid_cluster", "none"
    ] = "pchip"
    max_gap_frames: int = 10
    fill_edges: bool = False


@dataclass(slots=True)
class OpenSimScaleConfig:
    time_window: tuple[float, float] | str = "auto"
    preserve_mass_distribution: bool = False
    output_prefix: str | None = None


@dataclass(slots=True)
class OpenSimIKConfig:
    marker_weights: dict[str, float] = field(default_factory=dict)
    accuracy: float = 1e-5
    output_prefix: str | None = None


@dataclass(slots=True)
class OpenSimIDConfig:
    lowpass_cutoff_hz: float = -1.0
    output_prefix: str | None = None
