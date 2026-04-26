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
from .pipeline import (
    InverseDynamicsPipelineResult,
    MarkerToIDResult,
    VideoInverseDynamicsResult,
    VideoToIDResult,
    estimate_loads_from_pose,
    load_trc_to_id,
    markers_to_id,
    pose_to_trc,
    trc_to_id,
    trc_to_inverse_dynamics,
    video_to_id,
    video_to_inverse_dynamics,
    video_to_trc,
)
from .resources import (
    builtin_osim_model_path,
    builtin_pose_model_path,
    get_builtin_geometry_dir,
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
    "InverseDynamicsPipelineResult",
    "VideoInverseDynamicsResult",
    "MarkerToIDResult",
    "VideoToIDResult",
    "external",
    "video_to_trc",
    "trc_to_inverse_dynamics",
    "video_to_inverse_dynamics",
    "pose_to_trc",
    "markers_to_id",
    "trc_to_id",
    "load_trc_to_id",
    "video_to_id",
    "estimate_loads_from_pose",
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
    "get_builtin_geometry_dir",
    "builtin_osim_model_path",
    "builtin_pose_model_path",
    "get_builtin_osim_model",
    "list_builtin_osim_models",
]
