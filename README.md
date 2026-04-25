# monomech

`monomech` is a notebook-first Python library for single-camera biomechanics workflows. It helps you move from video or marker data into inspectable pose results, OpenSim-ready files, and analysis-friendly tables without hiding the intermediate steps.

The library is built around a practical workflow:

1. Load a video or TRC marker trial.
2. Estimate 2D pose and MediaPipe world landmarks when working from video.
3. Convert pose results into a global marker representation.
4. Export CSV and TRC files for inspection and downstream tools.
5. Run OpenSim scale, inverse kinematics, and inverse dynamics when OpenSim bindings are available.

## Installation

Base install:

```bash
python -m pip install monomech
```

Video pose estimation:

```bash
python -m pip install "monomech[pose]"
```

PyPI OpenSim-compatible bindings:

```bash
python -m pip install "monomech[opensim]"
```

Everything optional:

```bash
python -m pip install "monomech[all]"
```

For local development:

```bash
python -m pip install -e ".[dev]"
```

`monomech` currently supports Python 3.10 through 3.12.

## Quick Start

```python
import monomech as mm

trial = mm.load_video("subject01.mp4")

pose2d = trial.estimate_pose2d()
pose3d_world = trial.estimate_pose3d_world()
pose3d_global = trial.estimate_pose3d_global()

pose3d_global.to_csv("outputs/subject01_global.csv")
pose3d_global.to_trc("outputs/subject01_global.trc", model_path="model.osim")
```

For marker-first work:

```python
import monomech as mm

trial = mm.load_trc("walk.trc")
trial.clean_markers(cutoff_hz=6.0)
trial.to_trc("outputs/walk_clean.trc")
```

For bundled OpenSim model resources:

```python
import monomech as mm

model_path = mm.get_builtin_osim_model("pose")
print(model_path)
```

## OpenSim Workflow

OpenSim operations are available through trial methods:

```python
scale = trial.run_opensim_scale(
    model_path="model.osim",
    trc_path="outputs/subject01_global.trc",
)

ik = trial.run_opensim_ik(
    model_path=scale.scaled_model_path,
    trc_path="outputs/subject01_global.trc",
)

id_result = trial.run_opensim_id(
    model_path=scale.scaled_model_path,
    ik_path=ik.mot_path,
)
```

OpenSim itself can be installed through conda, or you can opt into the PyPI-compatible `pyopensim` binding with `monomech[opensim]`.

## What Ships

- `VideoTrial` and `MarkerTrial` objects for video-first and marker-first workflows
- pose estimation helpers for 2D, world 3D, and global 3D pose
- TRC loading/export
- OpenSim setup and execution helpers
- packaged OpenSim models and pose model resources
- notebook-friendly result objects with DataFrame and file export helpers

## Documentation

- [Getting started](docs/getting-started.md)
- [Outputs and files](docs/outputs.md)
- [OpenSim stage guide](docs/stages/opensim.md)
- [Publishing guide](docs/PUBLISHING.md)
- [Release guide](docs/RELEASING.md)

The documentation site is built with MkDocs and published through GitHub Pages.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
python -m build
```

## Publishing

GitHub Actions builds distributions on every push to `main`. PyPI publishing is triggered by version tags such as:

```bash
git tag v0.15.1
git push origin v0.15.1
```

The PyPI project must have a matching Trusted Publisher configured for `chags1313/monomech` and `.github/workflows/publish.yml`.

## License

See [LICENSE](LICENSE).
