# Getting Started

This page walks through the shortest reliable path from a fresh install to useful exported files. Follow the sections in order the first time, then use the stage pages when you want deeper control.

## 1. Create An Environment

Use Python 3.10, 3.11, or 3.12.

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
```

On macOS or Linux, activate with:

```bash
source .venv/bin/activate
```

## 2. Install The Right Extra

=== "Base import and TRC tools"

    ```bash
    python -m pip install monomech
    ```

=== "Single-camera pose"

    ```bash
    python -m pip install "monomech[pose]"
    ```

=== "OpenSim through PyPI"

    ```bash
    python -m pip install "monomech[opensim]"
    ```

=== "Notebooks and plots"

    ```bash
    python -m pip install "monomech[notebook]"
    ```

=== "All optional features"

    ```bash
    python -m pip install "monomech[all]"
    ```

## 3. Verify The Install

```python
import monomech as mm

print(mm.list_builtin_osim_models())
print(mm.get_builtin_osim_model("pose"))
```

If this imports successfully, the base package is installed correctly.

## 4. Prepare Your Files

Put raw inputs in a predictable folder before running notebooks or scripts.

```text
project/
  data/
    subject01.mp4
    walk.trc
  outputs/
  notebooks/
```

Keep one output folder per subject or trial. It makes CSV, TRC, OpenSim setup XML, and model files much easier to compare later.

## Video-First Workflow

Start here when your input is a single-camera video.

```python
from pathlib import Path
import monomech as mm

video_path = Path("data/subject01.mp4")
output_dir = Path("outputs/subject01")
output_dir.mkdir(parents=True, exist_ok=True)

trial = mm.load_video(video_path)
```

Estimate pose in stages:

```python
pose2d = trial.estimate_pose2d()
pose3d_world = trial.estimate_pose3d_world()
pose3d_global = trial.estimate_pose3d_global()
```

Inspect before exporting:

```python
print(pose2d.summary().head())
print(pose3d_global.to_wide_df().head())
```

Export files:

```python
pose3d_global.to_csv(output_dir / "subject01_global.csv")
trial.last_trc_path = pose3d_global.to_trc(output_dir / "subject01_global.trc")
```

Use the convenience wrapper when you want the common steps together:

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

Start here when you already have a TRC file.

```python
from pathlib import Path
import monomech as mm

trc_path = Path("data/walk.trc")
output_dir = Path("outputs/walk")
output_dir.mkdir(parents=True, exist_ok=True)

trial = mm.load_trc(trc_path)
```

Inspect markers:

```python
print(trial.marker_names[:10])
print(trial.sampling_rate)
print(trial.time_range)
trial.summary().head()
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

Run inverse dynamics only after inverse kinematics looks reasonable and you have the required external-load information:

```python
id_result = trial.run_opensim_id(
    model_path=scale.scaled_model_path,
    ik_path=ik.path,
    output_dir="outputs/subject01/id",
)
```

## Built-In Models

```python
import monomech as mm

print(mm.list_builtin_osim_models())
print(mm.get_builtin_osim_model("pose"))
print(mm.get_builtin_osim_model("mocap"))
```

Built-in model paths are regular local files, so they can be passed directly to trial methods.

## What To Check Before OpenSim

<div class="mono-path" markdown>
<div class="mono-step" markdown>
**Marker names**

Confirm exported marker names match the model marker names or provide a marker map.
</div>
<div class="mono-step" markdown>
**Coordinate scale**

Inspect the TRC values and units before scaling a model.
</div>
<div class="mono-step" markdown>
**Missing data**

Summarize or plot markers to catch long gaps before inverse kinematics.
</div>
<div class="mono-step" markdown>
**Time range**

Use a stable quiet window for scaling when the full trial contains extra movement.
</div>
</div>

## Troubleshooting

| Symptom | Likely fix |
| --- | --- |
| `import monomech` fails after a base install | Upgrade to `monomech>=0.15.1`; optional native dependencies should not be required for import. |
| Video pose methods are missing dependencies | Install `python -m pip install "monomech[pose]"`. |
| Notebook plotting fails | Install `python -m pip install "monomech[notebook]"`. |
| OpenSim import fails | Use a conda OpenSim install or install `python -m pip install "monomech[opensim]"`. |
| TRC export looks misaligned | Check marker names, units, axis mapping, and model compatibility before running IK. |

## Continue Learning

- [Example notebooks](examples.md)
- [Pose2D stage](stages/pose2d.md)
- [Global pose stage](stages/global-pose.md)
- [OpenSim stage](stages/opensim.md)
- [Outputs and files](outputs.md)
