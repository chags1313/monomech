from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from .animation import (
    OpenSimVisualizerResult,
    save_opensim_animation,
    save_opensim_visualizer,
)
from .config import (
    OpenSimIDConfig,
    OpenSimIKConfig,
    OpenSimScaleConfig,
    Pose2DConfig,
    Pose3DGlobalConfig,
)
from .external import ExternalLoadsSpec, external
from .io.trc import load_trc
from .opensim_api import run_id as _opensim_run_id
from .opensim_api import run_ik as _opensim_run_ik
from .opensim_api import run_scale as _opensim_run_scale
from .pipeline import VideoInverseDynamicsResult, video_to_inverse_dynamics
from .pose import estimate_global_pose, estimate_pose_from_video
from .resources import get_builtin_geometry_dir, get_builtin_osim_model
from .results import (
    BaseResult,
    MarkerResult,
    OpenSimScaleResult,
    PipelineRun,
    Pose3DGlobalResult,
    StorageResult,
)
from .utils import ensure_dir


def _resolve_model(model: str | Path | None) -> Path:
    if model is None:
        return get_builtin_osim_model("pose")
    if isinstance(model, str) and model in {"pose", "markers", "mocap"}:
        return get_builtin_osim_model("mocap" if model == "markers" else model)
    return Path(model).expanduser().resolve()


def _as_marker_result(markers: str | Path | MarkerResult | BaseResult) -> MarkerResult | BaseResult:
    if isinstance(markers, (str, Path)):
        trial = load_trc(markers)
        if trial.markers is None:
            raise ValueError(f"No markers were loaded from {markers}")
        return trial.markers
    return markers


def _write_markers_to_trc(
    markers: str | Path | MarkerResult | BaseResult,
    *,
    output_dir: str | Path,
    name: str | None = None,
    model_path: str | Path | None = None,
) -> Path:
    if isinstance(markers, (str, Path)):
        return Path(markers).expanduser().resolve()

    out = ensure_dir(output_dir)
    stem = name or getattr(markers, "name", "markers")
    trc_path = out / f"{stem}.trc"
    return markers.to_trc(trc_path, model_path=model_path)


def estimate_pose(
    video_path: str | Path,
    *,
    root_centered: bool = False,
    floored: bool = True,
    sample_fps: float | None = None,
    stride: int = 1,
    pose2d_config: Pose2DConfig | None = None,
    global_config: Pose3DGlobalConfig | None = None,
) -> Pose3DGlobalResult:
    """Estimate notebook-ready 3D pose from a video."""

    if pose2d_config is None:
        pose2d_config = Pose2DConfig(sample_fps=sample_fps, stride=stride)
    pose2d, pose3d_world = estimate_pose_from_video(video_path, config=pose2d_config)

    if global_config is None:
        global_config = Pose3DGlobalConfig(
            translation_method="hip_center" if root_centered else "pnp",
            smooth_root=True,
        )
    pose = estimate_global_pose(pose3d_world, pose2d, config=global_config)
    if not floored:
        pose.metadata = dict(pose.metadata or {})
        pose.metadata["floored"] = False
    pose.metadata = {
        **(pose.metadata or {}),
        "pose2d_result": pose2d,
        "pose3d_world_result": pose3d_world,
        "root_centered": bool(root_centered),
        "floored": bool(floored),
    }
    return pose


def smooth(
    data: str | Path | BaseResult,
    *,
    method: str = "butterworth",
    fps: float | None = None,
    cutoff_hz: float = 6.0,
    order: int = 4,
    window_length: int = 11,
    polyorder: int = 3,
    preserve_segment_lengths: bool = False,
):
    """Smooth pose, marker, or TRC data."""

    result = _as_marker_result(data)
    return result.smooth(
        method=method,
        fps=fps,
        cutoff_hz=cutoff_hz,
        order=order,
        window_length=window_length,
        polyorder=polyorder,
        preserve_segment_lengths=preserve_segment_lengths,
    )


def gap_fill(
    data: str | Path | BaseResult,
    *,
    method: str = "pchip",
    max_gap_frames: int = 10,
    fill_edges: bool = False,
):
    """Gap-fill pose, marker, or TRC data."""

    result = _as_marker_result(data)
    return result.gap_fill(method=method, max_gap_frames=max_gap_frames, fill_edges=fill_edges)


def run_scaling(
    markers: str | Path | BaseResult,
    *,
    model: str | Path | None = "pose",
    output_dir: str | Path = "outputs/scaling",
    name: str | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
    config: OpenSimScaleConfig | None = None,
) -> OpenSimScaleResult:
    """Scale an OpenSim model from markers or pose data."""

    model_path = _resolve_model(model)
    out = ensure_dir(output_dir)
    trc_path = _write_markers_to_trc(markers, output_dir=out, name=name, model_path=model_path)
    config = config or OpenSimScaleConfig()
    if start_time is not None or end_time is not None:
        trial = load_trc(trc_path)
        if trial.markers is None:
            raise ValueError(f"No markers found in TRC: {trc_path}")
        time = trial.markers.time
        t0 = float(time[0]) if start_time is None else float(start_time)
        t1 = float(time[-1]) if end_time is None else float(end_time)
        config.time_window = (t0, t1)
    result = _opensim_run_scale(
        trc_path=trc_path,
        model_path=model_path,
        output_dir=out,
        config=config,
    )
    result.metadata = {
        **(result.metadata or {}),
        "model_path": str(result.scaled_model_path),
        "unscaled_model_path": str(model_path),
        "trc_path": str(trc_path),
    }
    return result


def run_ik(
    scaled_model: OpenSimScaleResult | str | Path | None = None,
    *,
    markers: str | Path | BaseResult | None = None,
    model: str | Path | None = None,
    output_dir: str | Path = "outputs/ik",
    backend: Literal["base", "fast"] | None = None,
    config: OpenSimIKConfig | None = None,
) -> StorageResult:
    """Run inverse kinematics from a scaled model, model path, or markers."""

    trc_path: Path | None = None
    if isinstance(scaled_model, OpenSimScaleResult):
        model_path = scaled_model.scaled_model_path
        if scaled_model.metadata and scaled_model.metadata.get("trc_path"):
            trc_path = Path(scaled_model.metadata["trc_path"])
    else:
        model_path = _resolve_model(model or scaled_model)

    if markers is not None:
        trc_path = _write_markers_to_trc(markers, output_dir=output_dir, model_path=model_path)
    if trc_path is None:
        raise ValueError("Provide markers=... or pass a scaled model created by run_scaling().")

    config = config or OpenSimIKConfig()
    if backend is not None:
        config.backend = backend

    result = _opensim_run_ik(
        trc_path=trc_path,
        model_path=model_path,
        output_dir=output_dir,
        config=config,
    )
    result.metadata = {
        **(result.metadata or {}),
        "model_path": str(model_path),
        "trc_path": str(trc_path),
    }
    return result


def load(
    *,
    type: Literal["carried", "constant"] = "carried",
    body: str | None = None,
    applied_to_body: str | None = None,
    mass_kg: float | None = None,
    force: tuple[float, float, float] | None = None,
    point: tuple[float, float, float] = (0.0, 0.0, 0.0),
    start_time: float | None = None,
    end_time: float | None = None,
    name: str | None = None,
) -> ExternalLoadsSpec:
    """Create an external load with production-friendly defaults."""

    body_name = applied_to_body or body
    if body_name is None:
        raise ValueError("Provide body= or applied_to_body=.")
    if type == "carried":
        if mass_kg is None:
            raise ValueError("carried loads require mass_kg.")
        return external.carried_load(
            mass_kg=mass_kg,
            applied_to_body=body_name,
            point=point,
            start_time=start_time,
            end_time=end_time,
            name=name or "carried_load",
        )
    if type == "constant":
        if force is None:
            raise ValueError("constant loads require force=(Fx, Fy, Fz).")
        return external.constant_force(
            applied_to_body=body_name,
            force=force,
            point=point,
            start_time=start_time,
            end_time=end_time,
            name=name or "constant_load",
        )
    raise ValueError(f"Unsupported load type: {type}")


def estimate_grf(
    source: Pose3DGlobalResult | MarkerResult | PipelineRun | VideoInverseDynamicsResult,
    *,
    body_mass_kg: float = 75.0,
    method: str = "contact_vertical",
) -> list[ExternalLoadsSpec]:
    """Estimate ground reaction forces from pose or marker positions."""

    pose = source
    if isinstance(source, VideoInverseDynamicsResult):
        pose = source.trial.pose3d_global_result
    elif isinstance(source, PipelineRun):
        pose = source.pose3d_global
    if pose is None or isinstance(pose, StorageResult):
        raise ValueError("estimate_grf() needs pose or marker positions, not IK coordinates alone.")
    return external.estimate_grf(pose3d=pose, body_mass_kg=body_mass_kg, method=method)


def external_forces(
    *,
    loads: ExternalLoadsSpec
    | list[ExternalLoadsSpec]
    | tuple[ExternalLoadsSpec, ...]
    | None = None,
    include_estimated_grf: bool = False,
) -> list[ExternalLoadsSpec | str] | list[ExternalLoadsSpec] | None:
    """Compose external loads for inverse dynamics."""

    if loads is None:
        load_list: list[ExternalLoadsSpec] = []
    elif isinstance(loads, ExternalLoadsSpec):
        load_list = [loads]
    else:
        load_list = list(loads)
    if include_estimated_grf:
        return external.with_estimated_grf(load_list)
    return load_list or None


def run_id(
    *,
    ik: StorageResult | str | Path,
    external_forces: ExternalLoadsSpec
    | list[ExternalLoadsSpec]
    | list[ExternalLoadsSpec | str]
    | None = None,
    model: str | Path | None = None,
    output_dir: str | Path = "outputs/id",
    config: OpenSimIDConfig | None = None,
) -> StorageResult:
    """Run inverse dynamics from IK coordinates and optional external forces."""

    ik_path = ik.path if isinstance(ik, StorageResult) else Path(ik).expanduser().resolve()
    model_hint = model
    if model_hint is None and isinstance(ik, StorageResult):
        model_hint = (ik.metadata or {}).get("model_path")
    model_path = _resolve_model(model_hint)
    result = _opensim_run_id(
        ik_path=ik_path,
        model_path=model_path,
        output_dir=output_dir,
        external_forces=external_forces,
        config=config,
    )
    result.metadata = {
        **(result.metadata or {}),
        "model_path": str(model_path),
        "ik_path": str(ik_path),
    }
    return result


def animate(
    *,
    ik: StorageResult | str | Path,
    id: StorageResult | str | Path | None = None,
    model: str | Path | None = None,
    output_dir: str | Path = "outputs/visualizer",
    name: str | None = None,
    external_loads_path: str | Path | None = None,
    create_glb: bool = True,
    render: Literal["fast", "glb"] = "glb",
    mode: Literal["preview", "balanced", "final"] = "balanced",
    stride: int | None = None,
    decimate_target_reduction: float | None = None,
    decimate_error: float | None = None,
    thin_pos_tol: float | None = 1e-4,
    thin_rot_tol_deg: float | None = 0.05,
    drop_static_nodes: bool = False,
    drop_origin_nodes: bool = False,
    max_frames: int = 240,
    marker_stride: int = 1,
    embed_glb: bool = False,
    include_markers: bool = True,
    bodies: Literal["all", "major"] | list[str] | tuple[str, ...] | None = "all",
    cache: bool = True,
    cache_path: str | Path | None = None,
) -> OpenSimVisualizerResult:
    """Create a notebook-ready OpenSim animation visualizer."""

    if render not in {"fast", "glb"}:
        raise ValueError("render must be either 'fast' or 'glb'.")
    if render == "fast":
        create_glb = False
        max_frames = min(int(max_frames), 120)

    ik_path = ik.path if isinstance(ik, StorageResult) else Path(ik).expanduser().resolve()
    id_path = (
        None
        if id is None
        else (id.path if isinstance(id, StorageResult) else Path(id).expanduser().resolve())
    )
    metadata = ik.metadata if isinstance(ik, StorageResult) else None
    model_path = _resolve_model(model or (metadata or {}).get("model_path"))
    out = ensure_dir(output_dir)
    stem = name or ik_path.stem.replace("_ik", "")
    presets = {
        "preview": {
            "stride": 3,
            "decimate_target_reduction": 0.55,
            "marker_stride": max(2, marker_stride),
            "max_frames": min(max_frames, 160),
        },
        "balanced": {
            "stride": 2,
            "decimate_target_reduction": 0.35,
            "marker_stride": marker_stride,
            "max_frames": max_frames,
        },
        "final": {
            "stride": 1,
            "decimate_target_reduction": None,
            "marker_stride": marker_stride,
            "max_frames": max_frames,
        },
    }
    if mode not in presets:
        raise ValueError("mode must be one of: 'preview', 'balanced', or 'final'.")
    preset = presets[mode]
    animation_stride = int(stride or preset["stride"])
    animation_decimation = (
        decimate_target_reduction
        if decimate_target_reduction is not None
        else preset["decimate_target_reduction"]
    )
    viewer_marker_stride = int(preset["marker_stride"])
    viewer_max_frames = int(preset["max_frames"])

    glb_path = None
    marker_dataframe = None
    if create_glb:
        animation = save_opensim_animation(
            osim_path=model_path,
            geom_dir=get_builtin_geometry_dir(),
            mot_path=ik_path,
            id_path=id_path,
            external_loads_path=external_loads_path,
            out_glb_path=out / f"{stem}.glb",
            stride=animation_stride,
            thin_pos_tol=thin_pos_tol,
            thin_rot_tol_deg=thin_rot_tol_deg,
            drop_static_nodes=drop_static_nodes,
            decimate_target_reduction=animation_decimation,
            decimate_error=decimate_error,
            drop_origin_nodes=drop_origin_nodes,
        )
        glb_path = animation.glb_path
        marker_dataframe = animation.marker_dataframe

    return save_opensim_visualizer(
        out / f"{stem}.html",
        osim_path=model_path,
        ik_path=ik_path,
        id_path=id_path,
        external_loads_path=external_loads_path,
        glb_path=glb_path,
        marker_dataframe=marker_dataframe,
        max_frames=viewer_max_frames,
        marker_stride=viewer_marker_stride,
        embed_glb=embed_glb,
        include_markers=include_markers,
        bodies=bodies,
        cache=cache,
        cache_path=cache_path,
    )


def fast_viewer(
    *,
    ik: StorageResult | str | Path,
    id: StorageResult | str | Path | None = None,
    model: str | Path | None = None,
    output_dir: str | Path = "outputs/visualizer",
    name: str | None = None,
    external_loads_path: str | Path | None = None,
    max_frames: int = 240,
    marker_stride: int = 1,
    include_markers: bool = True,
    bodies: Literal["all", "major"] | list[str] | tuple[str, ...] | None = "all",
    cache: bool = True,
    cache_path: str | Path | None = None,
) -> OpenSimVisualizerResult:
    """Create the fast no-GLB OpenSim viewer."""

    return animate(
        ik=ik,
        id=id,
        model=model,
        output_dir=output_dir,
        name=name,
        external_loads_path=external_loads_path,
        render="fast",
        max_frames=max_frames,
        marker_stride=marker_stride,
        include_markers=include_markers,
        bodies=bodies,
        cache=cache,
        cache_path=cache_path,
    )


def video_pipeline(*args: Any, **kwargs: Any) -> VideoInverseDynamicsResult:
    """Production-friendly alias for the full video-to-ID pipeline."""

    return video_to_inverse_dynamics(*args, **kwargs)


def marker_pipeline(
    markers: str | Path | BaseResult,
    *,
    model: str | Path | None = "pose",
    output_dir: str | Path = "outputs/marker_pipeline",
    smooth: bool = True,
    gap_fill: bool = True,
    forces: ExternalLoadsSpec | list[ExternalLoadsSpec] | None = None,
):
    """Run marker/TRC data through cleanup, scaling, IK, ID, and visualization."""

    marker_data = _as_marker_result(markers)
    if gap_fill:
        marker_data = marker_data.gap_fill()
    if smooth:
        marker_data = marker_data.smooth()
    scaled = run_scaling(marker_data, model=model, output_dir=Path(output_dir) / "scale")
    ik = run_ik(scaled, output_dir=Path(output_dir) / "ik")
    id_result = run_id(ik=ik, external_forces=forces, output_dir=Path(output_dir) / "id")
    viewer = animate(
        ik=ik,
        id=id_result,
        output_dir=Path(output_dir) / "visualizer",
        external_loads_path=None
        if id_result.metadata is None
        else id_result.metadata.get("external_loads_mot_path"),
    )
    return {
        "markers": marker_data,
        "scaled_model": scaled,
        "ik": ik,
        "id": id_result,
        "animation": viewer,
    }
