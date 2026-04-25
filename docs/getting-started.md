# Getting Started

This guide walks through the shortest path from installation to a useful exported result.

## Install

Base install:

```bash
python -m pip install monomech
```

For video pose estimation, install the pose extra:

```bash
python -m pip install "monomech[pose]"
```

For OpenSim-compatible PyPI bindings:

```bash
python -m pip install "monomech[opensim]"
```

For development:

```bash
python -m pip install -e ".[dev]"
```

## Import

```python
import monomech as mm
```

## Video-First Workflow

```python
trial = mm.load_video("subject01.mp4")

pose2d = trial.estimate_pose2d()
pose3d_world = trial.estimate_pose3d_world()
pose3d_global = trial.estimate_pose3d_global()
```

Export analysis-friendly and OpenSim-friendly files:

```python
pose3d_global.to_csv("outputs/subject01_global.csv")
pose3d_global.to_trc("outputs/subject01_global.trc", model_path="model.osim")
```

Run the bundled convenience pipeline when you want the common steps together:

```python
run = trial.run_pipeline(
    export_csv=True,
    export_trc=True,
    model_path="model.osim",
    output_dir="outputs/subject01",
)
```

## Marker-First Workflow

```python
trial = mm.load_trc("walk.trc")

trial.clean_markers(
    gap_fill_method="rigid_cluster",
    gap_fill_max_frames=20,
    cutoff_hz=6.0,
)

trial.to_trc("outputs/walk_clean.trc")
```

## OpenSim

```python
scale = trial.run_opensim_scale(
    model_path="model.osim",
    trc_path="outputs/subject01_global.trc",
)

ik = trial.run_opensim_ik(
    model_path=scale.scaled_model_path,
    trc_path="outputs/subject01_global.trc",
)
```

If OpenSim is installed through conda, `monomech` will try to use the official `opensim` Python package. If you use the PyPI binding, install `monomech[opensim]`.

## Built-In Models

```python
model_path = mm.get_builtin_osim_model("pose")
models = mm.list_builtin_osim_models()
```

Built-in model names currently include:

- `pose`
- `mocap`

## Troubleshooting

If `import monomech` fails after a base install, reinstall from version `0.15.1` or newer. Native video/OpenSim dependencies are optional extras and should not be required for a base import.
