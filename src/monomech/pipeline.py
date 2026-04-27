from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .animation import (
    OpenSimAnimationResult,
    OpenSimVisualizerResult,
    save_opensim_animation,
    save_opensim_visualizer,
)
from .config import OpenSimIDConfig, OpenSimIKConfig, Pose2DConfig, Pose3DGlobalConfig
from .core.trials import VideoTrial
from .external import ExternalLoadsSpec, external
from .io.trc import load_trc
from .io.video import load_video
from .opensim_api import run_id, run_ik
from .results import PipelineRun, Pose3DGlobalResult, StorageResult
from .utils import ensure_dir


@dataclass(slots=True)
class InverseDynamicsPipelineResult:
    """Results from TRC markers through OpenSim IK and inverse dynamics."""

    trc_path: Path
    ik: StorageResult
    id: StorageResult
    external_forces: ExternalLoadsSpec | list[ExternalLoadsSpec] | None = None
    metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class VideoInverseDynamicsResult:
    """Results from video pose through TRC, IK, inverse dynamics, and optional visualization."""

    trial: VideoTrial
    pose: PipelineRun
    trc_path: Path
    ik: StorageResult
    id: StorageResult
    animation: OpenSimAnimationResult | None = None
    visualizer: OpenSimVisualizerResult | None = None
    external_forces: ExternalLoadsSpec | list[ExternalLoadsSpec] | None = None
    metadata: dict[str, Any] | None = None


def video_to_trc(
    video_path: str | Path,
    *,
    output_dir: str | Path = "outputs",
    name: str | None = None,
    model_path: str | Path | None = None,
    sample_fps: float | None = None,
    stride: int = 1,
    pose2d_config: Pose2DConfig | None = None,
    global_config: Pose3DGlobalConfig | None = None,
    export_csv: bool = True,
) -> PipelineRun:
    """Run video pose estimation and write a TRC file in one call."""

    trial = load_video(video_path, name=name)
    out = ensure_dir(Path(output_dir).expanduser().resolve())

    if pose2d_config is None:
        trial.estimate_pose2d(fps=sample_fps, stride=stride)
    else:
        trial.estimate_pose2d(config=pose2d_config)
    trial.estimate_pose3d_world()
    trial.estimate_pose3d_global(config=global_config)

    run = PipelineRun(
        pose2d=trial.pose2d_result,
        pose3d_world=trial.pose3d_world_result,
        pose3d_global=trial.pose3d_global_result,
    )
    if export_csv:
        run.csv_paths = trial.export_csvs(output_dir=out)
    if trial.pose3d_global_result is None:
        raise RuntimeError("Global 3D pose was not created.")
    trc_path = out / f"{trial.name}.trc"
    run.trc_path = trial.pose3d_global_result.to_trc(trc_path, model_path=model_path)
    trial.last_trc_path = run.trc_path
    return run


def trc_to_inverse_dynamics(
    trc_path: str | Path,
    *,
    model_path: str | Path,
    output_dir: str | Path = "outputs",
    external_forces: ExternalLoadsSpec | list[ExternalLoadsSpec] | None = None,
    ik_config: OpenSimIKConfig | None = None,
    id_config: OpenSimIDConfig | None = None,
) -> InverseDynamicsPipelineResult:
    """Run OpenSim IK and inverse dynamics from a marker TRC in one call."""

    trc = Path(trc_path).expanduser().resolve()
    model = Path(model_path).expanduser().resolve()
    out = ensure_dir(Path(output_dir).expanduser().resolve())
    ik = run_ik(trc_path=trc, model_path=model, output_dir=out / "ik", config=ik_config)
    inverse_dynamics = run_id(
        ik_path=ik.path,
        model_path=model,
        output_dir=out / "id",
        external_forces=external_forces,
        config=id_config,
    )
    return InverseDynamicsPipelineResult(
        trc_path=trc,
        ik=ik,
        id=inverse_dynamics,
        external_forces=external_forces,
        metadata={
            "model_path": str(model),
            "output_dir": str(out),
            "external_loads_xml_path": inverse_dynamics.metadata.get("external_loads_xml_path")
            if inverse_dynamics.metadata
            else None,
            "external_loads_mot_path": inverse_dynamics.metadata.get("external_loads_mot_path")
            if inverse_dynamics.metadata
            else None,
        },
    )


def video_to_inverse_dynamics(
    video_path: str | Path,
    *,
    model_path: str | Path,
    output_dir: str | Path = "outputs",
    name: str | None = None,
    geom_dir: str | Path | None = None,
    sample_fps: float | None = None,
    stride: int = 1,
    external_forces: ExternalLoadsSpec
    | list[ExternalLoadsSpec]
    | Literal["estimate"]
    | None = "estimate",
    body_mass_kg: float = 75.0,
    pose2d_config: Pose2DConfig | None = None,
    global_config: Pose3DGlobalConfig | None = None,
    ik_config: OpenSimIKConfig | None = None,
    id_config: OpenSimIDConfig | None = None,
    create_animation: bool = True,
    create_visualizer: bool = True,
) -> VideoInverseDynamicsResult:
    """Run the full video-to-inverse-dynamics pipeline in one call."""

    trial = load_video(video_path, name=name)
    out = ensure_dir(Path(output_dir).expanduser().resolve())
    model = Path(model_path).expanduser().resolve()

    if pose2d_config is None:
        trial.estimate_pose2d(fps=sample_fps, stride=stride)
    else:
        trial.estimate_pose2d(config=pose2d_config)
    trial.estimate_pose3d_world()
    trial.estimate_pose3d_global(config=global_config)
    pose_run = PipelineRun(
        pose2d=trial.pose2d_result,
        pose3d_world=trial.pose3d_world_result,
        pose3d_global=trial.pose3d_global_result,
        csv_paths=trial.export_csvs(output_dir=out / "pose"),
    )
    if trial.pose3d_global_result is None:
        raise RuntimeError("Global 3D pose was not created.")
    pose_run.trc_path = trial.pose3d_global_result.to_trc(
        out / f"{trial.name}.trc",
        model_path=model,
    )
    trial.last_trc_path = pose_run.trc_path

    loads: ExternalLoadsSpec | list[ExternalLoadsSpec] | None
    if external_forces == "estimate":
        loads = external.estimate_grf(
            pose3d=trial.pose3d_global_result,
            body_mass_kg=body_mass_kg,
        )
    else:
        loads = external_forces

    marker_id = trc_to_inverse_dynamics(
        pose_run.trc_path,
        model_path=model,
        output_dir=out / "opensim",
        external_forces=loads,
        ik_config=ik_config,
        id_config=id_config,
    )

    animation = None
    visualizer = None
    external_loads_path = None
    if marker_id.id.metadata:
        external_loads_path = marker_id.id.metadata.get("external_loads_mot_path")

    if create_animation:
        animation = save_opensim_animation(
            osim_path=model,
            geom_dir=geom_dir,
            mot_path=marker_id.ik.path,
            id_path=marker_id.id.path,
            external_loads_path=external_loads_path,
            out_glb_path=out / "visualizer" / f"{trial.name}_ik.glb",
        )

    if create_visualizer:
        visualizer = save_opensim_visualizer(
            out / "visualizer" / f"{trial.name}_ik_id.html",
            osim_path=model,
            ik_path=marker_id.ik.path,
            id_path=marker_id.id.path,
            external_loads_path=external_loads_path,
            glb_path=None if animation is None else animation.glb_path,
        )

    return VideoInverseDynamicsResult(
        trial=trial,
        pose=pose_run,
        trc_path=pose_run.trc_path,
        ik=marker_id.ik,
        id=marker_id.id,
        animation=animation,
        visualizer=visualizer,
        external_forces=loads,
        metadata={
            "model_path": str(model),
            "output_dir": str(out),
            "external_loads_mot_path": external_loads_path,
        },
    )


MarkerToIDResult = InverseDynamicsPipelineResult
VideoToIDResult = VideoInverseDynamicsResult


def pose_to_trc(*args, **kwargs) -> PipelineRun:
    """Alias for `video_to_trc()`."""

    return video_to_trc(*args, **kwargs)


def markers_to_id(*args, **kwargs) -> InverseDynamicsPipelineResult:
    """Alias for `trc_to_inverse_dynamics()`."""

    return trc_to_inverse_dynamics(*args, **kwargs)


def video_to_id(*args, **kwargs) -> VideoInverseDynamicsResult:
    """Alias for `video_to_inverse_dynamics()`."""

    return video_to_inverse_dynamics(*args, **kwargs)


def trc_to_id(*args, **kwargs) -> InverseDynamicsPipelineResult:
    """Alias for `trc_to_inverse_dynamics()`."""

    return trc_to_inverse_dynamics(*args, **kwargs)


def load_trc_to_id(
    trc_path: str | Path,
    *,
    model_path: str | Path,
    output_dir: str | Path = "outputs",
    external_forces: ExternalLoadsSpec | list[ExternalLoadsSpec] | None = None,
    ik_config: OpenSimIKConfig | None = None,
    id_config: OpenSimIDConfig | None = None,
) -> InverseDynamicsPipelineResult:
    """Load a TRC, validate it as markers, then run IK and ID."""

    load_trc(trc_path)
    return trc_to_inverse_dynamics(
        trc_path,
        model_path=model_path,
        output_dir=output_dir,
        external_forces=external_forces,
        ik_config=ik_config,
        id_config=id_config,
    )


def estimate_loads_from_pose(
    pose3d: Pose3DGlobalResult,
    *,
    body_mass_kg: float = 75.0,
) -> list[ExternalLoadsSpec]:
    """Create estimated bilateral ground-reaction loads from a global pose result."""

    return external.estimate_grf(pose3d=pose3d, body_mass_kg=body_mass_kg)
