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
    geom_dir="Geometry",
)

print(result.glb_path)
print(result.metadata["node_count"])
```

If `geom_dir` is omitted, `monomech` looks next to the model for `Geometry/`, `geometry/`, and then the model directory itself.

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

trial = mm.load_video("data/subject01.mp4")
run = trial.run_pipeline(export_csv=True, export_trc=True, output_dir="outputs/subject01")

model_path = mm.get_builtin_osim_model("pose")

scale = trial.run_opensim_scale(
    model_path=model_path,
    trc_path=run.trc_path,
    output_dir="outputs/subject01/scale",
)

ik = trial.run_opensim_ik(
    model_path=scale.scaled_model_path,
    trc_path=run.trc_path,
    output_dir="outputs/subject01/ik",
)

loads = mm.external.estimate_grf(
    pose3d=run.pose3d_global,
    body_mass_kg=75.0,
)

id_result = trial.run_opensim_id(
    model_path=scale.scaled_model_path,
    ik_path=ik.path,
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

Write a lightweight local viewer for the GLB:

```python
viewer = mm.save_animation_viewer(
    "outputs/subject01/animation/viewer.html",
    animation.glb_path,
)

print(viewer)
```

Open `viewer.html` in a browser to inspect the animation.

## File Size And Speed

Use these knobs when the GLB is too large or export takes too long:

| Option | What it does |
| --- | --- |
| `stride=2` | Exports every second IK frame. Higher values make smaller files. |
| `thin_pos_tol=1e-4` | Removes translation keyframes that barely change. |
| `thin_rot_tol_deg=0.05` | Removes rotation keyframes that barely change. |
| `drop_static_nodes=True` | Stores static body geometry with one keyframe. |
| `drop_origin_nodes=True` | Drops unresolved nodes sitting at the origin. |
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
| No geometry is exported | Pass `geom_dir=` pointing at the OpenSim `Geometry` folder. |
| GLB contains unresolved parts at the origin | Keep `drop_origin_nodes=True` or inspect `result.metadata["missing_geometry"]`. |
| Animation looks too slow or too fast | Check the IK MOT time column and selected `t_start`, `t_end`, and `stride`. |
| File is too large | Increase `stride`, use keyframe thinning, or set `decimate_target_reduction`. |
