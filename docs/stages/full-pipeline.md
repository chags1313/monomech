# Full Pipeline Wrapper

The trial-level pipeline wrapper runs the common video workflow in one call while still returning stage outputs.

```python
trial = mm.load_video("subject01.mp4")

run = trial.run_pipeline(
    pose2d=True,
    pose3d_world=True,
    pose3d_global=True,
    export_csv=True,
    export_trc=True,
    model_path="model.osim",
    output_dir="outputs/subject01",
)
```

## Returned Object

The returned `PipelineRun` can contain:

- `pose2d`
- `pose3d_world`
- `pose3d_global`
- `csv_paths`
- `trc_path`

## When To Use It

Use `run_pipeline()` for repeatable processing once you know the settings you want.

Use the individual stage methods when you are exploring data, debugging model fit, or tuning smoothing/export settings.
