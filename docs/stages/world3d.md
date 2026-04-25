# World 3D Pose

The world 3D stage exposes MediaPipe world landmarks as a `Pose3DWorldResult`.

```python
trial = mm.load_video("subject01.mp4")
trial.estimate_pose2d()
pose3d_world = trial.estimate_pose3d_world()
```

If 2D pose has not already been estimated, `estimate_pose3d_world()` will run the pose stage first.

## Smoothing

```python
pose3d_world = trial.estimate_pose3d_world(smooth=True)
```

The default workflow applies a Butterworth smoothing pass when smoothing is enabled.

## Outputs

```python
pose3d_world.to_csv("outputs/subject01_world.csv")
world_df = pose3d_world.to_dataframe()
```
