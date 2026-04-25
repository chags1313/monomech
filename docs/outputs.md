# Outputs and Files

`monomech` result objects are designed to be inspectable in notebooks and useful in downstream tools.

## Common Result Methods

Most pose and marker results provide:

- `to_dataframe()` for long-form analysis tables
- `to_wide_df()` for wide-form tables
- `to_csv(path)` for CSV export
- `to_trc(path, model_path=...)` where marker/TRC export is supported
- `summary()` for quick quality checks
- `.smooth(...)` and `.gap_fill(...)` on compatible results

## Video Pipeline Outputs

```python
trial = mm.load_video("subject01.mp4")
run = trial.run_pipeline(
    export_csv=True,
    export_trc=True,
    model_path="model.osim",
    output_dir="outputs/subject01",
)
```

Typical files:

```text
outputs/subject01/
  subject01_pose2d.csv
  subject01_pose3d_world.csv
  subject01_pose3d_global.csv
  subject01.trc
```

## Marker Pipeline Outputs

```python
trial = mm.load_trc("walk.trc")
trial.clean_markers()
trial.to_trc("outputs/walk_clean.trc")
```

Typical files:

```text
outputs/
  walk_clean.trc
```

## OpenSim Outputs

Scale, IK, and ID methods write OpenSim setup files and result files into stage-specific directories by default:

```text
outputs/
  subject01/
    scale/
      *_scale_setup.xml
      *_scaled.osim
    ik/
      *_ik_setup.xml
      *_ik.mot
      _ik_marker_errors.sto
    id/
      *_id_setup.xml
      *_id.sto
      *_ExternalLoads.xml
```

Exact names depend on the source trial and OpenSim stage configuration.

## Recommended Layout

Use one output directory per subject or trial:

```text
outputs/
  subject01_walk/
    pose/
    scale/
    ik/
    id/
  subject02_walk/
    pose/
    scale/
    ik/
    id/
```

This keeps intermediate pose data, exported TRC files, and OpenSim results together without mixing subjects.
