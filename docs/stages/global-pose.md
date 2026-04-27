# Global Pose

The global pose stage converts world landmarks into a floor-aligned representation that can be exported to CSV or TRC.

```python
pose3d_global = mm.estimate_pose(
    "subject01.mp4",
    root_centered=False,
    floored=True,
)
```

## Export

```python
pose3d_global.to_csv("outputs/subject01_global.csv")
pose3d_global.to_trc("outputs/subject01_global.trc", model_path="model.osim")
```

## Configuration

```python
config = mm.Pose3DGlobalConfig(
    translation_method="pnp",
    smooth_root=True,
)

pose3d_global = mm.estimate_pose("subject01.mp4", global_config=config)
```

## Common Uses

- inspect whole-body motion in a common coordinate frame
- create TRC files for OpenSim workflows
- compare trials using consistent landmark names and timing
