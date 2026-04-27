# OpenSim Animation Export

`monomech` can export an animated OpenSim model to a single `.glb` file after inverse kinematics. The GLB contains the model geometry, the IK-driven animation, and optional inverse-dynamics metadata.

Use this when you want a portable file for review, presentation, web viewing, or sharing a quick motion result without opening the OpenSim GUI.

## Install

Animation export needs optional 3D dependencies:

```bash
python -m pip install "monomech[animation]"
```

This extra includes OpenSim bindings, `pyvista`, and `pygltflib`.

## Basic Export

```python
import monomech as mm

result = mm.save_opensim_animation(
    osim_path="outputs/subject01/scale/subject01_scaled.osim",
    mot_path="outputs/subject01/ik/subject01_ik.mot",
    out_glb_path="outputs/subject01/animation/subject01_motion.glb",
)

print(result.glb_path)
print(result.metadata["node_count"])
```

If `geom_dir` is omitted, `monomech` first uses its packaged full-body geometry, then looks next to the model for `Geometry/`, `geometry/`, and the model directory itself. Pass `geom_dir` only when using a custom model or mesh folder. For full-body models downloaded from zip archives, make sure this points at the real mesh folder, not a `__MACOSX` metadata folder. A good folder contains real `.vtp`, `.obj`, or `.stl` mesh files, not tiny `._name.vtp` files.

## IK And ID Together

Pass the inverse-dynamics output with `id_path`. The GLB animation is still driven by IK coordinates, while ID metadata is embedded in the file extras.

```python
result = mm.save_opensim_animation(
    osim_path=scale.scaled_model_path,
    mot_path=ik.path,
    id_path=id_result.path,
    out_glb_path="outputs/subject01/animation/subject01_ik_id.glb",
)

print(result.metadata["id_summary"])
```

The GLB stays a single portable file, and the returned result keeps the export summary available in Python.

## From A Full Pipeline

```python
import monomech as mm

pose = mm.estimate_pose("data/subject01.mp4")
pose = mm.gap_fill(mm.smooth(pose))

scale = mm.run_scaling(
    pose,
    model="pose",
    output_dir="outputs/subject01/scale",
)

ik = mm.run_ik(scale, output_dir="outputs/subject01/ik")

loads = mm.estimate_grf(pose, body_mass_kg=75.0)

id_result = mm.run_id(
    ik=ik,
    external_forces=loads,
    output_dir="outputs/subject01/id",
)

animation = mm.save_opensim_animation(
    osim_path=scale.scaled_model_path,
    mot_path=ik.path,
    id_path=id_result.path,
    out_glb_path="outputs/subject01/animation/subject01_ik_id.glb",
    stride=2,
    decimate_target_reduction=0.35,
)
```

That is the complete review path: video in, pose tracking, OpenSim scale, IK, external loads, ID, and a browser-ready animated model out.

## Geometry Folder Checklist

The GLB exporter uses the OpenSim model file for body transforms and the geometry folder for visual meshes. If the animation plays but the body is invisible or incomplete, check these first:

| Check | What to do |
| --- | --- |
| Real mesh files are present | Open the folder and confirm files such as `r_pelvis.vtp`, `femur_r.vtp`, or similar are normal-sized files. |
| Avoid `__MACOSX` folders | Those folders usually contain `._*.vtp` metadata files and are not usable mesh geometry. |
| Match model and geometry family | Use the `Geometry/` folder that came with the `.osim` model whenever possible. |
| Packaged geometry | The default full-body meshes are included with `monomech`. |
| Pass `geom_dir` explicitly | Do this when using custom model geometry or a different mesh set. |
| Start with a preview export | Use `stride=3` and `decimate_target_reduction=0.5`, then lower those settings for final review. |

## Marker Positions

By default, the exporter also returns a DataFrame of model marker positions through time:

```python
markers = animation.to_dataframe()
display(markers.head())
```

Disable this when you only need the GLB:

```python
animation = mm.save_opensim_animation(
    osim_path=scale.scaled_model_path,
    mot_path=ik.path,
    out_glb_path="outputs/subject01/animation/subject01.glb",
    return_markers=False,
)
```

## HTML Viewer

Write a lightweight local Three.js viewer for the GLB:

```python
viewer = mm.save_animation_viewer(
    "outputs/subject01/animation/viewer.html",
    animation.glb_path,
)

print(viewer)
```

Open `viewer.html` in a browser to inspect the animation. By default, the GLB is embedded into the HTML when you provide `glb_path`, so the model appears immediately in notebooks, local files, and shared HTML exports. The viewer also has an **Upload GLB** control, so you can reuse the same page with a new exported model.

## Notebook IK/ID Dashboard

For notebooks and review sessions, use `save_opensim_visualizer()`. It creates a richer Three.js HTML dashboard with:

- animated OpenSim GLB mesh playback when a model is available
- a 3D marker/skeleton fallback
- external-force arrows from the generated external-load `.mot`
- synchronized IK coordinate plots
- inverse-dynamics trace plots
- a browser-side **Upload GLB** control for GitHub Pages and notebook sharing

```python
viewer = mm.save_opensim_visualizer(
    "outputs/subject01/animation/ik_id_viewer.html",
    osim_path=scale.scaled_model_path,
    ik_path=ik.path,
    id_path=id_result.path,
    external_loads_path=id_result.metadata["external_loads_mot_path"],
    glb_path=animation.glb_path,
    title="subject01 IK + ID",
)

viewer
```

In Jupyter, display the visualizer with one call:

```python
mm.display_visualizer(viewer)
```

Pipeline results expose the same shortcut:

```python
result.display()
```

When you already have IK and ID result objects from the staged API, `animate()` is the shortest path:

```python
animation = mm.animate(
    ik=ik,
    id=id_result,
    external_loads_path=id_result.metadata["external_loads_mot_path"],
    output_dir="outputs/subject01/visualizer",
)

animation.show()
```

In a script, open `viewer.html` in a browser.

The same visualizer works well on GitHub Pages because it does not need a Python server. The online page lets readers upload their own `.glb` export directly in the browser:

You can also build the dashboard without mesh geometry:

```python
marker_df = mm.extract_opensim_marker_positions(
    osim_path=scale.scaled_model_path,
    mot_path=ik.path,
    stride=2,
)

viewer = mm.save_opensim_visualizer(
    "outputs/subject01/animation/marker_force_viewer.html",
    marker_dataframe=marker_df,
    ik_path=ik.path,
    id_path=id_result.path,
    external_loads_path=id_result.metadata["external_loads_mot_path"],
)
```

[Open the online GLB visualizer](../assets/visualizer.html){ .md-button }

## External Forces In The Viewer

When `external_loads_path` is provided, the dashboard reads the external-load `.mot` and displays force vectors as orange arrows in the 3D scene. The expected columns follow OpenSim-style force and point naming:

```text
time right_vx right_vy right_vz right_px right_py right_pz
```

Each load needs velocity/force components ending in `_vx`, `_vy`, `_vz` and matching point columns ending in `_px`, `_py`, `_pz`. The viewer interpolates those vectors onto the displayed marker frames, scales the arrows for readability, and keeps them synchronized with the IK and ID plots.

For estimated ground-reaction forces from `mm.external.estimate_grf()`, monomech remaps pose axes into the same OpenSim-friendly coordinate system used by TRC export (`X=z`, `Y=y`, `Z=x`) and grounds the vertical axis before writing external loads. That keeps force application points aligned with the IK model rather than the original camera coordinate frame.

```python
viewer = mm.save_opensim_visualizer(
    "outputs/subject01/animation/forces_viewer.html",
    marker_dataframe=animation.marker_dataframe,
    ik_path=ik.path,
    id_path=id_result.path,
    external_loads_path="outputs/subject01/id/subject01_external_loads.mot",
    glb_path=animation.glb_path,
)
```

## File Size And Speed

Use these knobs when the GLB is too large or export takes too long:

| Option | What it does |
| --- | --- |
| `stride=2` | Exports every second IK frame. Higher values make smaller files. |
| `thin_pos_tol=1e-4` | Removes translation keyframes that barely change. |
| `thin_rot_tol_deg=0.05` | Removes rotation keyframes that barely change. |
| `drop_static_nodes=False` | Keeps complete animation tracks for every exported mesh by default. Set to `True` for smaller review files. |
| `drop_origin_nodes=False` | Keeps every resolved mesh in the scene by default. Set to `True` only when diagnosing unresolved geometry sitting at the origin. |
| `decimate_target_reduction=0.35` | Reduces mesh triangle count before writing GLB. |

For fast previews, start with:

```python
animation = mm.save_opensim_animation(
    osim_path=scale.scaled_model_path,
    mot_path=ik.path,
    out_glb_path="outputs/subject01/animation/preview.glb",
    stride=3,
    decimate_target_reduction=0.5,
)
```

For final review, reduce or remove decimation and use `stride=1`.

## Compatibility Wrapper

Older notebooks can keep using the original call shape:

```python
marker_df = mm.save_ik_animation(
    "model.osim",
    "Geometry",
    "ik.mot",
    "motion.glb",
)
```

New code should prefer `save_opensim_animation()` because it returns paths, metadata, and marker data together.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Missing optional dependency error | Install `python -m pip install "monomech[animation]"`. |
| No geometry is exported | Confirm the model uses compatible mesh names, or pass `geom_dir=` for a custom OpenSim geometry folder. |
| GLB contains unresolved parts at the origin | Try `drop_origin_nodes=True` for diagnostic exports, then inspect `result.metadata["missing_geometry"]` and the geometry folder path. |
| Animation looks too slow or too fast | Check the IK MOT time column and selected `t_start`, `t_end`, and `stride`. |
| File is too large | Increase `stride`, use keyframe thinning, or set `decimate_target_reduction`. |
