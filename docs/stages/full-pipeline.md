# Full Pipeline Wrapper

The trial-level pipeline wrapper runs the common video pose workflow in one call while still returning stage outputs. Use it after you have already stepped through the staged workflow once.

## Video To TRC

```python
import monomech as mm

trial = mm.load_video("data/subject01.mp4")

run = trial.run_pipeline(
    pose2d=True,
    pose3d_world=True,
    pose3d_global=True,
    export_csv=True,
    export_trc=True,
    output_dir="outputs/subject01",
)
```

## Returned Object

The returned `PipelineRun` can contain:

| Attribute | Meaning |
| --- | --- |
| `pose2d` | 2D landmark result. |
| `pose3d_world` | MediaPipe world landmark result. |
| `pose3d_global` | Global 3D pose result suitable for export. |
| `csv_paths` | CSV files written during export. |
| `trc_path` | OpenSim-ready TRC path. |

## Video To Inverse Dynamics

OpenSim scale, IK, external loads, and ID are intentionally separate from `run_pipeline()` because those stages usually require model checks and force assumptions.

```python
import monomech as mm

trial = mm.load_video("data/subject01.mp4")

run = trial.run_pipeline(
    export_csv=True,
    export_trc=True,
    output_dir="outputs/subject01",
)

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

estimated_loads = mm.external.estimate_grf(
    pose3d=run.pose3d_global,
    body_mass_kg=75.0,
)

id_result = trial.run_opensim_id(
    model_path=scale.scaled_model_path,
    ik_path=ik.path,
    external_forces=estimated_loads,
    output_dir="outputs/subject01/id",
)

print(id_result.path)
```

## What To Inspect At Each Stop

| Step | Check |
| --- | --- |
| Pose result | Landmark coverage, obvious tracking failures, frame rate, and time vector. |
| TRC export | Marker names, units, axes, and missing values. |
| Scale | Scaled model path, setup XML, log, and `scale.metadata["preflight"]`. |
| IK | `ik.metadata["marker_error_summary"]` and coordinate plots. |
| External loads | Generated MOT/XML, force signs, center-of-pressure units, and time alignment. |
| ID | STO columns, sign conventions, and whether moments are plausible for the task. |

## When To Use It

Use `run_pipeline()` for repeatable video-to-TRC processing once you know the settings you want.

Use individual stage methods when you are exploring data, debugging model fit, tuning smoothing/export settings, or adding external loads for inverse dynamics.
