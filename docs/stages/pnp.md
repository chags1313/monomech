# PnP

`monomech` uses a PnP-style translation option inside the global pose stage when image-space and world landmarks are available.

```python
pose3d_global = mm.estimate_pose(
    "subject01.mp4",
    global_config=mm.Pose3DGlobalConfig(translation_method="pnp"),
)
```

Use `root_centered=True` in `estimate_pose()` when you want hip-centered translation instead of PnP-based global translation.

## Fallback Behavior

If OpenCV is unavailable or PnP cannot be applied for a frame, the global pose logic can fall back to hip-centered translation behavior.

## When To Use It

Use PnP when you want a camera-aware root translation estimate from a monocular video. Use hip-centered translation when you want a simpler root-normalized representation.
