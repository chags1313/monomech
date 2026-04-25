# monomech

`monomech` is a notebook-first biomechanics library for turning single-camera video and marker data into inspectable tables, OpenSim-ready files, and reproducible analysis artifacts.

It is designed for researchers and developers who want a clear path through the workflow without losing access to the intermediate data.

## Core Workflow

```python
import monomech as mm

trial = mm.load_video("subject01.mp4")

pose2d = trial.estimate_pose2d()
pose3d_world = trial.estimate_pose3d_world()
pose3d_global = trial.estimate_pose3d_global()

pose3d_global.to_csv("outputs/subject01_global.csv")
pose3d_global.to_trc("outputs/subject01_global.trc", model_path="model.osim")
```

## What monomech Gives You

- video-first and marker-first trial objects
- explicit pose, smoothing, gap-filling, TRC, and OpenSim steps
- result objects that convert cleanly to DataFrames and files
- packaged OpenSim and pose model resources
- optional native dependencies so base installs remain importable

## Installation

Base install:

```bash
python -m pip install monomech
```

Video pose support:

```bash
python -m pip install "monomech[pose]"
```

OpenSim-compatible PyPI bindings:

```bash
python -m pip install "monomech[opensim]"
```

All optional runtime dependencies:

```bash
python -m pip install "monomech[all]"
```

## Workflows

| Workflow | Entry point | Main outputs |
| --- | --- | --- |
| Video to pose | `mm.load_video()` | 2D pose, world 3D pose, global 3D pose |
| Marker cleanup | `mm.load_trc()` | cleaned marker tables, TRC |
| OpenSim scale/IK/ID | trial OpenSim methods | setup XML, scaled model, MOT/STO files |
| Packaged resources | `mm.get_builtin_osim_model()` | stable local model paths |

## Next Steps

- [Getting started](getting-started.md)
- [Video workflow](stages/pose2d.md)
- [Marker and TRC outputs](outputs.md)
- [OpenSim guide](stages/opensim.md)
- [FAQ](FAQ.md)
