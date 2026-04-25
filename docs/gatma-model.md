# GATMA Model Guide

`monomech` can be used with custom OpenSim models, including GATMA-style workflows, as long as the exported TRC marker names match the model markers expected by OpenSim.

## Inspect Model Markers

```python
import monomech as mm

markers = mm.inspect_model_markers("GATMA_Model.osim")
markers.head()
```

## Build a Marker Map

```python
trial = mm.load_trc("walk.trc")

marker_map = trial.build_marker_map("GATMA_Model.osim")
```

Use the marker map as a review tool before running OpenSim scale or IK.

## Video to TRC

```python
trial = mm.load_video("subject01.mp4")

trial.estimate_pose2d()
trial.estimate_pose3d_world()
global_pose = trial.estimate_pose3d_global()

trc_path = global_pose.to_trc(
    "outputs/subject01_global.trc",
    model_path="GATMA_Model.osim",
)
```

## OpenSim

```python
scale = trial.run_opensim_scale(
    model_path="GATMA_Model.osim",
    trc_path=trc_path,
    output_dir="outputs/subject01/scale",
)

ik = trial.run_opensim_ik(
    model_path=scale.scaled_model_path,
    trc_path=trc_path,
    output_dir="outputs/subject01/ik",
)
```

## Practical Checks

- Confirm units before exporting TRC.
- Confirm marker names against the OpenSim model.
- Inspect IK marker errors before running inverse dynamics.
- Keep scale, IK, and ID outputs in separate folders.
