# API Reference

This page summarizes the public API in the order most notebooks use it. The short functions are the main workflow; advanced functions are listed near the end for custom file-oriented jobs.

## Install Extras

| API area | Extra |
| --- | --- |
| `import monomech`, TRC I/O, metadata helpers | base install |
| `estimate_pose()` and video pose methods | `monomech[pose]` |
| `run_scaling()`, `run_ik()`, `run_id()` | `monomech[opensim]` |
| `animate()` and GLB export | `monomech[animation]` |
| `vis_2d()`, `vis_3d()`, `plot()` in notebooks | `monomech[notebook]` |

```bash
python -m pip install "monomech[all]"
```

## Notebook-First Workflow

```python
import monomech as mm

pose = mm.estimate_pose("data/subject01.mp4")
pose = mm.smooth(pose)
pose = mm.gap_fill(pose)

scaled_model = mm.run_scaling(pose, model="pose")
ik = mm.run_ik(scaled_model)

grf = mm.estimate_grf(pose, body_mass_kg=75.0)
id_result = mm.run_id(ik=ik, external_forces=grf)

viewer = mm.animate(ik=ik, id=id_result)
viewer.show()
```

## Pose And Marker Data

### `estimate_pose(video_path, *, root_centered=False, floored=True, sample_fps=None, stride=1, pose2d_config=None, global_config=None)`

Estimate a global 3D pose result from a video.

Returns: `Pose3DGlobalResult`

```python
pose = mm.estimate_pose(
    "data/squat.mp4",
    root_centered=False,
    floored=True,
    sample_fps=30,
)
```

Use `root_centered=True` when you want pose motion centered around the pelvis instead of camera-positioned global motion. Use `floored=True` for OpenSim-friendly ground contact.

### `smooth(data, *, method="butterworth", cutoff_hz=6.0, order=4, window_length=11, polyorder=3, preserve_segment_lengths=False)`

Smooth a pose result, marker result, or TRC path.

```python
pose_smoothed = mm.smooth(pose, cutoff_hz=6.0)
markers_smoothed = mm.smooth("data/walk.trc", method="savgol")
```

Supported methods include `butterworth`, `savgol`, `median`, and `confidence_weighted`.

### `gap_fill(data, *, method="pchip", max_gap_frames=10, fill_edges=False)`

Fill short gaps in pose or marker trajectories.

```python
pose_filled = mm.gap_fill(pose_smoothed, max_gap_frames=12)
```

Methods include `linear`, `pchip`, `cubic_spline`, and `nearest_valid`. Marker trial helpers also expose `rigid_cluster` and `rigid_segment` names for workflow readability.

## Result Methods

Pose and marker result objects expose:

| Method | Purpose |
| --- | --- |
| `.to_wide_df()` | One row per frame with one column per signal. |
| `.to_long_df()` | Tidy long-form table. |
| `.to_csv(path)` | Write the result to CSV. |
| `.to_trc(path, model_path=None)` | Write an OpenSim TRC. |
| `.summary()` | Missing-data and confidence summary by landmark. |
| `.qc_report()` | Quality-control report object. |
| `.vis_2d(frame=...)` | 2D skeleton preview; overlays on the source video frame when available. |
| `.vis_3d(frame=...)` | White-background 3D skeleton preview with model Y as vertical. |

```python
pose.vis_2d(frame=50)
pose.vis_3d(frame=50)
pose.to_csv("outputs/subject01/pose.csv")
pose.to_trc("outputs/subject01/pose.trc")
```

Pass `image=False` to `vis_2d()` for a skeleton-only white background, or pass an image array with `image=...` to draw on a specific frame.

OpenSim storage results from IK and ID expose:

| Method | Purpose |
| --- | --- |
| `.to_dataframe()` | Return a pandas DataFrame. |
| `.to_csv(path)` | Write the storage table to CSV. |
| `.plot(columns=None)` | Plot selected signals. |
| `.summary()` | Numeric summary by signal. |

```python
ik.plot()
id_result.plot(columns=["hip_flexion_r_moment"])
id_result.to_csv("outputs/subject01/id.csv")
```

## OpenSim

### `run_scaling(markers, *, model="pose", output_dir="outputs/scaling", name=None, start_time=None, end_time=None, config=None)`

Scale an OpenSim model from a pose result, marker result, or TRC file.

Returns: `OpenSimScaleResult`

```python
scaled_model = mm.run_scaling(
    pose,
    model="pose",
    output_dir="outputs/subject01/scale",
)
```

`model` can be a built-in name such as `"pose"` or `"mocap"`, or a path to a custom `.osim` file.

### `run_ik(scaled_model=None, *, markers=None, model=None, output_dir="outputs/ik", config=None)`

Run inverse kinematics.

Returns: `StorageResult`

```python
ik = mm.run_ik(scaled_model, output_dir="outputs/subject01/ik")
```

You can also pass explicit markers and a model:

```python
ik = mm.run_ik(
    markers="outputs/subject01/pose.trc",
    model="models/subject01_scaled.osim",
)
```

### `run_id(*, ik, external_forces=None, model=None, output_dir="outputs/id", config=None)`

Run inverse dynamics from IK coordinates.

Returns: `StorageResult`

```python
id_result = mm.run_id(
    ik=ik,
    external_forces=forces,
    output_dir="outputs/subject01/id",
)
```

If `ik` was produced by `run_ik()`, the model path is carried in metadata. Pass `model=` explicitly when using an IK file from another source.

## External Loads

### `load(type="carried", *, body=None, applied_to_body=None, mass_kg=None, force=None, point=(0, 0, 0), start_time=None, end_time=None, name=None)`

Create a simple external load.

```python
dumbbell = mm.load(
    type="carried",
    body="hand_r",
    mass_kg=10.0,
)
```

When `start_time` and `end_time` are left unset, the load is active for the full IK trial passed to `mm.run_id()`. Pass both values for a time-limited load.

For a constant force:

```python
push = mm.load(
    type="constant",
    body="hand_r",
    force=(25.0, 0.0, 0.0),
    start_time=0.5,
    end_time=1.5,
)
```

### `estimate_grf(source, *, body_mass_kg=75.0, method="contact_vertical")`

Estimate bilateral ground-reaction loads from pose or marker positions.

```python
grf = mm.estimate_grf(pose, body_mass_kg=75.0)
```

Estimated GRF is useful for pipeline testing and exploratory workflows. Use measured forces for scientific interpretation of kinetics.

### `external_forces(loads=None, *, include_estimated_grf=False)`

Compose loads for inverse dynamics.

```python
forces = mm.external_forces(loads=[dumbbell, *grf])
id_result = mm.run_id(ik=ik, external_forces=forces)
```

For the one-line video pipeline, you can request estimated GRF inside the pipeline:

```python
forces = mm.external_forces(loads=[dumbbell], include_estimated_grf=True)
```

### `mm.external`

The `mm.external` factory exposes lower-level constructors:

| Method | Use when |
| --- | --- |
| `from_dataframe(...)` | Your force data is already in pandas. |
| `from_csv(...)` | Your force data is in a CSV file. |
| `from_timeseries(...)` | You have NumPy arrays for time, force, point, and torque. |
| `constant_force(...)` | You want a fixed force over a time interval. |
| `carried_load(...)` | You want a fixed downward load from an object. |
| `estimate_grf(...)` | You want estimated vertical foot contact loads. |
| `with_estimated_grf(...)` | You want the full video pipeline to add estimated GRF around extra loads. |

## Animation And Visualization

### `animate(*, ik, id=None, model=None, output_dir="outputs/visualizer", name=None, external_loads_path=None, create_glb=True, mode="balanced", stride=None, decimate_target_reduction=None, decimate_error=None, thin_pos_tol=1e-4, thin_rot_tol_deg=0.05, drop_static_nodes=False, drop_origin_nodes=False, max_frames=240, marker_stride=1, embed_glb=False)`

Create a notebook-ready Three.js visualizer.

Returns: `OpenSimVisualizerResult`

```python
viewer = mm.animate(
    ik=ik,
    id=id_result,
    external_loads_path=id_result.metadata["external_loads_mot_path"],
    mode="balanced",
)
viewer.show()
```

The visualizer can show the animated GLB mesh, marker fallback, force arrows, IK traces, and ID traces. By default, the HTML references a sibling GLB file instead of embedding it, which keeps notebooks and docs responsive. Use `embed_glb=True` only when you need a single self-contained HTML file.

In Jupyter, `viewer.show()` injects the GLB into the displayed copy of the viewer as a browser blob, so the notebook does not have to fetch a local sibling file.

| Mode | Behavior |
| --- | --- |
| `preview` | Faster export for quick notebook checks. |
| `balanced` | Default quality and size balance. |
| `final` | Full-frame, non-decimated animation. |

### Advanced Animation Functions

| Function | Purpose |
| --- | --- |
| `save_opensim_animation(...)` | Export OpenSim IK motion to GLB. |
| `save_opensim_visualizer(...)` | Write the full IK/ID HTML dashboard. |
| `save_animation_viewer(...)` | Write a lightweight GLB-only viewer. |
| `display_visualizer(...)` | Display an existing visualizer in Jupyter. |

## Full Pipelines

### `video_pipeline(...)`

Alias for `video_to_inverse_dynamics(...)`.

```python
result = mm.video_pipeline(
    "data/subject01.mp4",
    model_path=mm.get_builtin_osim_model("pose"),
    output_dir="outputs/subject01",
)
result.display()
```

### `marker_pipeline(markers, *, model="pose", output_dir="outputs/marker_pipeline", smooth=True, gap_fill=True, forces=None)`

Run marker/TRC data through cleanup, scaling, IK, ID, and visualization.

```python
result = mm.marker_pipeline(
    "data/walk.trc",
    model="mocap",
    output_dir="outputs/walk",
    forces=None,
)

result["animation"].show()
```

## Advanced File-Oriented Pipeline Functions

These functions are useful in scripts and production jobs where explicit paths are easier to manage:

| Function | Purpose |
| --- | --- |
| `video_to_trc(...)` | Video to pose CSVs and TRC. |
| `trc_to_inverse_dynamics(...)` | TRC to IK and ID. |
| `video_to_inverse_dynamics(...)` | Full video to pose, TRC, IK, ID, GLB, and visualizer. |
| `pose_to_trc(...)` | Alias for `video_to_trc(...)`. |
| `markers_to_id(...)` | Alias for `trc_to_inverse_dynamics(...)`. |
| `video_to_id(...)` | Alias for `video_to_inverse_dynamics(...)`. |

## Model And File Helpers

| Function | Purpose |
| --- | --- |
| `list_builtin_osim_models()` | List packaged model names. |
| `get_builtin_osim_model(name="pose")` | Get a stable local `.osim` path. |
| `get_builtin_geometry_dir()` | Get packaged OpenSim geometry. |
| `inspect_model_markers(model_path)` | Return model marker names and metadata. |
| `build_marker_map(source_markers, model_markers)` | Build a marker-name review map. |
| `load_marker_dataframe(df)` | Create a marker trial from a DataFrame. |

## Config Objects

Pass config objects when you need reproducible settings beyond the short function defaults:

| Config | Used by |
| --- | --- |
| `Pose2DConfig` | `estimate_pose()`, video trial pose estimation. |
| `Pose3DGlobalConfig` | global pose conversion. |
| `OpenSimScaleConfig` | `run_scaling()`. |
| `OpenSimIKConfig` | `run_ik()`. |
| `OpenSimIDConfig` | `run_id()`. |
| `ButterworthConfig` | smoothing workflows. |
| `GapFillConfig` | gap-fill workflows. |

```python
from monomech import OpenSimIKConfig

ik = mm.run_ik(
    scaled_model,
    config=OpenSimIKConfig(accuracy=1e-5, sanitize_marker_data=True),
)
```
