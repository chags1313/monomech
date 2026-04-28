# Online Visualizer

Use the browser visualizer to inspect a monomech `.glb` animation without installing Python. The page starts empty and waits for a file you choose. The file stays in your browser; it is not uploaded to a server.

[Open the GLB visualizer](assets/visualizer.html){ .md-button .md-button--primary }

The same viewer is available from Python:

```python
mm.glb_viewer().show()
```

To open a specific GLB from a notebook:

```python
viewer = mm.glb_viewer("outputs/subject01/visualizer/walk.glb")
viewer.show()
```

If the notebook browser cannot access that file path, use inline mode:

```python
viewer.show(inline_glb=True)
```

## What It Shows

- animated OpenSim mesh playback from a monomech-exported GLB
- playback controls, timeline scrubbing, orbit controls, and model visibility controls
- marker, force, IK, and ID panels when those data are embedded in an exported monomech dashboard

For a full exported dashboard with synchronized markers, external forces, IK plots, and ID plots, create it from Python:

```python
viewer = mm.animate(
    ik=ik,
    id=id_result,
    output_dir="outputs/subject01/visualizer",
    external_loads_path=id_result.metadata["external_loads_mot_path"],
)
viewer.show()
```

`animate()` focuses on creating the animation and exported dashboard. The returned viewer also keeps the model marker positions used for the display:

```python
model_markers = viewer.to_dataframe()
display(model_markers.head())
```
