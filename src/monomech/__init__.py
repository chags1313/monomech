"""MonoMech public API."""

from .animation import (
    OpenSimAnimationResult,
    OpenSimVisualizerResult,
    extract_opensim_marker_positions,
    save_animation_viewer,
    save_ik_animation,
    save_opensim_animation,
    save_opensim_visualizer,
    show_ik_animation,
)
from .config import (
    ButterworthConfig,
    GapFillConfig,
    OpenSimIDConfig,
    OpenSimIKConfig,
    OpenSimScaleConfig,
    Pose2DConfig,
    Pose3DGlobalConfig,
    Pose3DWorldConfig,
)
from .core.study import Study
from .core.trials import BaseTrial, MarkerTrial, VideoTrial
from .external import ExternalLoadsSpec, external
from .io.model import build_marker_map, inspect_model_markers
from .io.trc import load_marker_dataframe, load_trc
from .io.video import load_video, load_videos
from .resources import (
    builtin_osim_model_path,
    builtin_pose_model_path,
    get_builtin_osim_model,
    list_builtin_osim_models,
)
from .viz import install_plot_methods

install_plot_methods()

__all__ = [
    "BaseTrial",
    "VideoTrial",
    "MarkerTrial",
    "Study",
    "ExternalLoadsSpec",
    "external",
    "OpenSimAnimationResult",
    "OpenSimVisualizerResult",
    "extract_opensim_marker_positions",
    "save_opensim_animation",
    "save_opensim_visualizer",
    "save_ik_animation",
    "save_animation_viewer",
    "show_ik_animation",
    "load_video",
    "load_videos",
    "load_trc",
    "load_marker_dataframe",
    "inspect_model_markers",
    "build_marker_map",
    "Pose2DConfig",
    "Pose3DWorldConfig",
    "Pose3DGlobalConfig",
    "OpenSimScaleConfig",
    "OpenSimIKConfig",
    "OpenSimIDConfig",
    "ButterworthConfig",
    "GapFillConfig",
    "builtin_osim_model_path",
    "builtin_pose_model_path",
    "builtin_osim_model_path",
    "builtin_pose_model_path",
    "get_builtin_osim_model",
    "list_builtin_osim_models",
]
