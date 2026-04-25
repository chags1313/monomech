# PnP

`monomech` uses a PnP-style translation option inside the global pose stage when image-space and world landmarks are available.

```python
trial = mm.load_video("subject01.mp4")

pose2d = trial.estimate_pose2d()
pose3d_world = trial.estimate_pose3d_world()

pose3d_global = trial.estimate_pose3d_global(
    pose2d=pose2d,
    world_pose=pose3d_world,
    translation_method="pnp",
)
```

## Fallback Behavior

If OpenCV is unavailable or PnP cannot be applied for a frame, the global pose logic can fall back to hip-centered translation behavior.

## When To Use It

Use PnP when you want a camera-aware root translation estimate from a monocular video. Use hip-centered translation when you want a simpler root-normalized representation.
