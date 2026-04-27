# Model Guide

`monomech` includes packaged OpenSim models for common workflows, and it can also run with your own OpenSim model as long as the exported TRC marker names match the markers expected by the model.

Use this page when you need to choose a built-in model, inspect model markers, connect a custom model, or troubleshoot missing geometry.

## Built-In Models

```python
import monomech as mm

mm.list_builtin_osim_models()
```

Current built-ins:

| Name | Use when |
| --- | --- |
| `pose` | You are starting from MediaPipe-style video pose landmarks. |
| `mocap` | You are starting from a more traditional marker/TRC workflow. |

Get a stable local model path:

```python
model_path = mm.get_builtin_osim_model("pose")
geometry_dir = mm.get_builtin_geometry_dir()

print(model_path)
print(geometry_dir)
```

The default `pose` model keeps its display geometry references. The packaged geometry folder is included with the wheel, so most users do not need to download or pass a geometry folder.

## Inspect Model Markers

```python
import monomech as mm

markers = mm.inspect_model_markers(mm.get_builtin_osim_model("pose"))
markers.head()
```

For a custom model:

```python
markers = mm.inspect_model_markers("models/custom_full_body.osim")
display(markers.head(30))
```

## Build a Marker Map

```python
trial = mm.load_trc("walk.trc")

marker_map = trial.build_marker_map("models/custom_full_body.osim")
```

Use the marker map as a review tool before running OpenSim scale or IK.

## Video to TRC

The short notebook workflow can export a pose result directly to TRC:

```python
pose = mm.estimate_pose("subject01.mp4", root_centered=False, floored=True)
pose = mm.gap_fill(mm.smooth(pose))

trc_path = pose.to_trc(
    "outputs/subject01_global.trc",
    model_path="models/custom_full_body.osim",
)
```

Use `marker_map=` when your pose or marker names need to be translated into model marker names.

## OpenSim

```python
scale = mm.run_scaling(
    trc_path,
    model="models/custom_full_body.osim",
    output_dir="outputs/subject01/scale",
)

ik = mm.run_ik(
    scale,
    output_dir="outputs/subject01/ik",
)
```

The lower-level trial methods are still available if you prefer explicit control:

```python
trial = mm.load_trc(trc_path)
ik = trial.run_opensim_ik(
    model_path=scale.scaled_model_path,
    trc_path=trc_path,
    output_dir="outputs/subject01/ik",
)
```

## Geometry For Animation

`mm.animate()` and `mm.save_opensim_animation()` need model geometry to draw the mesh. For built-in models, the packaged geometry is used automatically. For custom models, use the geometry folder that came with the model:

```python
viewer = mm.animate(
    ik=ik,
    model="models/custom_full_body.osim",
    output_dir="outputs/subject01/visualizer",
)
viewer.show()
```

If a custom model uses a separate mesh folder:

```python
animation = mm.save_opensim_animation(
    osim_path="models/custom_full_body.osim",
    geom_dir="models/Geometry",
    mot_path=ik.path,
    out_glb_path="outputs/subject01/visualizer/subject01.glb",
)
```

## Practical Checks

- Confirm units before exporting TRC.
- Confirm marker names against the OpenSim model.
- Inspect IK marker errors before running inverse dynamics.
- Keep scale, IK, and ID outputs in separate folders.
- For custom geometry, avoid `__MACOSX` folders from zip archives; those usually contain metadata files, not usable meshes.
