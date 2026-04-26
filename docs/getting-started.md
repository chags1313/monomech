# Getting Started

This guide takes you from a fresh environment to useful files. Run the sections in order the first time, then jump to the stage pages when you need deeper control.

## 1. Create An Environment

Use Python 3.10, 3.11, or 3.12.

=== "Windows"

    ```bash
    python -m venv .venv
    .venv\Scripts\activate
    python -m pip install --upgrade pip
    ```

=== "macOS / Linux"

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    ```

## 2. Install The Right Extra

| Need | Command |
| --- | --- |
| Import package, read/write TRC, use utilities | `python -m pip install monomech` |
| Estimate pose from video | `python -m pip install "monomech[pose]"` |
| Run OpenSim from Python | `python -m pip install "monomech[opensim]"` |
| Use notebooks and plots | `python -m pip install "monomech[notebook]"` |
| Install all optional features | `python -m pip install "monomech[all]"` |

## 3. Verify The Install

```python
import monomech as mm

print(mm.list_builtin_osim_models())
print(mm.get_builtin_osim_model("pose"))
```

If this imports successfully, the base package is working.

!!! note "Why extras are separate"
    Video and OpenSim dependencies can include native packages. Keeping them optional makes `import monomech` reliable on more computers.

## 4. Organize Files

Keep raw data and generated outputs separate:

```text
project/
  data/
    subject01.mp4
    walk.trc
    right_force_plate.csv
  outputs/
    subject01/
  notebooks/
```

Use one output folder per trial. It makes OpenSim setup XML, logs, TRC files, MOT files, and STO outputs much easier to compare.

## Video-First Workflow

Use this path when your starting point is a single-camera video.

```python
from pathlib import Path
import monomech as mm

video_path = Path("data/subject01.mp4")
output_dir = Path("outputs/subject01")
output_dir.mkdir(parents=True, exist_ok=True)

trial = mm.load_video(video_path)
```

Run stages separately while learning:

```python
pose2d = trial.estimate_pose2d()
pose3d_world = trial.estimate_pose3d_world()
pose3d_global = trial.estimate_pose3d_global()

print(pose2d.summary().head())
print(pose3d_global.to_wide_df().head())
```

Export the global pose:

```python
pose3d_global.to_csv(output_dir / "subject01_global.csv")
trc_path = pose3d_global.to_trc(output_dir / "subject01_global.trc")
```

Once the staged run makes sense, use the wrapper:

```python
run = trial.run_pipeline(
    export_csv=True,
    export_trc=True,
    output_dir=output_dir,
)

print(run.csv_paths)
print(run.trc_path)
```

## Marker-First Workflow

Use this path when you already have a TRC file.

```python
from pathlib import Path
import monomech as mm

trc_path = Path("data/walk.trc")
output_dir = Path("outputs/walk")
output_dir.mkdir(parents=True, exist_ok=True)

trial = mm.load_trc(trc_path)
```

Inspect markers before cleaning:

```python
print(trial.marker_names[:10])
print(trial.sampling_rate)
print(trial.time_range)
display(trial.summary().head())
```

Clean and export:

```python
trial.clean_markers(
    gap_fill_method="rigid_cluster",
    gap_fill_max_frames=20,
    cutoff_hz=6.0,
)

clean_trc = trial.to_trc(output_dir / "walk_clean.trc")
print(clean_trc)
```

## OpenSim Workflow

OpenSim steps work after you have a TRC file and a compatible model.

```python
import monomech as mm

model_path = mm.get_builtin_osim_model("pose")
trc_path = "outputs/subject01/subject01_global.trc"

scale = trial.run_opensim_scale(
    model_path=model_path,
    trc_path=trc_path,
    output_dir="outputs/subject01/scale",
)

ik = trial.run_opensim_ik(
    model_path=scale.scaled_model_path,
    trc_path=trc_path,
    output_dir="outputs/subject01/ik",
)
```

Review IK before inverse dynamics:

```python
display(ik.to_dataframe().head())
print(ik.metadata["marker_error_summary"])
print(ik.metadata["preflight"])
```

Add external loads for inverse dynamics:

```python
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

!!! warning "Estimated forces are for workflow testing"
    `estimate_grf()` is useful for examples and rough exploratory runs. Use measured force plates or another validated force source when kinetics need to be interpreted scientifically.

## Built-In Models

```python
import monomech as mm

print(mm.list_builtin_osim_models())
print(mm.get_builtin_osim_model("pose"))
print(mm.get_builtin_osim_model("mocap"))
```

Built-in model paths are regular local files, so they can be passed directly to OpenSim helpers.

## What To Check Before OpenSim

<div class="mono-path" markdown>
<div class="mono-step" markdown>
**Marker names**

Confirm exported marker names match the model marker names or provide a marker map.
</div>
<div class="mono-step" markdown>
**Units and axes**

Inspect TRC values before scaling. A unit or axis mismatch can make IK technically run but biomechanically meaningless.
</div>
<div class="mono-step" markdown>
**Missing data**

Read the preflight reports and check any all-missing marker channels before trusting the results.
</div>
<div class="mono-step" markdown>
**Time range**

Use stable time windows for scaling and make sure force data covers the IK interval.
</div>
</div>

## Troubleshooting

| Symptom | Likely fix |
| --- | --- |
| `import monomech` fails after a base install | Upgrade to `monomech>=0.15.1`; optional native dependencies should not be required for import. |
| Video pose methods complain about missing packages | Install `python -m pip install "monomech[pose]"`. |
| OpenSim cannot import | Use a conda OpenSim install or install `python -m pip install "monomech[opensim]"`. |
| IK fails on NaNs | Keep `OpenSimIKConfig(sanitize_marker_data=True)` or clean the TRC before running IK. |
| ID fails on coordinate NaNs | Keep `OpenSimIDConfig(sanitize_coordinates=True)` or clean the IK MOT before running ID. |
| ID runs but forces look wrong | Check force signs, units, centers of pressure, `applied_to_body`, and time alignment. |
| TRC export looks misaligned | Check marker names, axis mapping, units, and model compatibility before running IK. |

## Continue Learning

- [Example notebooks](examples.md)
- [External loads and forces](stages/forces.md)
- [OpenSim scale, IK, and ID](stages/opensim.md)
- [Full video-to-ID pipeline](stages/full-pipeline.md)
- [Outputs and files](outputs.md)
