# monomech

[![CI](https://github.com/chags1313/monomech/actions/workflows/ci.yml/badge.svg)](https://github.com/chags1313/monomech/actions/workflows/ci.yml)
[![Docs](https://github.com/chags1313/monomech/actions/workflows/docs.yml/badge.svg)](https://github.com/chags1313/monomech/actions/workflows/docs.yml)
[![Pages](https://github.com/chags1313/monomech/actions/workflows/docs.yml/badge.svg)](https://github.com/chags1313/monomech/actions/workflows/docs.yml)

`monomech` is a notebook-first Python library for single-camera biomechanics workflows. It helps you move from video or marker data into inspectable pose results, OpenSim-ready files, and analysis-friendly tables without hiding the intermediate steps.

Read the full documentation at [chags1313.github.io/monomech](https://chags1313.github.io/monomech/).

## What It Does

- Loads single-camera videos and TRC marker files.
- Estimates 2D pose, MediaPipe world landmarks, and global 3D pose.
- Exports wide/long CSV files and OpenSim-friendly TRC files.
- Cleans marker data with gap filling and smoothing.
- Provides helpers for OpenSim scale, inverse kinematics, and inverse dynamics.
- Ships bundled model resources so examples and tests have stable local paths.

## Install

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

Notebooks and plotting:

```bash
python -m pip install "monomech[notebook]"
```

Everything optional:

```bash
python -m pip install "monomech[all]"
```

`monomech` currently supports Python 3.10 through 3.12.

## Five-Minute Workflow

```python
from pathlib import Path
import monomech as mm

video_path = Path("data/subject01.mp4")
output_dir = Path("outputs/subject01")
output_dir.mkdir(parents=True, exist_ok=True)

trial = mm.load_video(video_path)

pose2d = trial.estimate_pose2d()
pose3d_world = trial.estimate_pose3d_world()
pose3d_global = trial.estimate_pose3d_global()

pose3d_global.to_csv(output_dir / "subject01_global.csv")
pose3d_global.to_trc(output_dir / "subject01_global.trc")
```

For marker-first work:

```python
from pathlib import Path
import monomech as mm

trial = mm.load_trc("data/walk.trc")
print(trial.summary())

trial.clean_markers(cutoff_hz=6.0)
trial.to_trc(Path("outputs/walk/walk_clean.trc"))
```

## Example Notebooks

The `examples/` folder includes ready-to-edit notebooks:

- [`video_to_trc_quickstart.ipynb`](examples/video_to_trc_quickstart.ipynb) for video to pose to CSV/TRC.
- [`marker_trc_cleanup.ipynb`](examples/marker_trc_cleanup.ipynb) for TRC inspection, cleaning, and export.
- [`opensim_scale_ik_template.ipynb`](examples/opensim_scale_ik_template.ipynb) for OpenSim scale and inverse kinematics setup.
- [`video_to_inverse_dynamics_pipeline.ipynb`](examples/video_to_inverse_dynamics_pipeline.ipynb) for video to inverse dynamics with estimated external loads.
- [`run_video_smoke.py`](examples/run_video_smoke.py) for repeatable command-line smoke tests.

Each notebook keeps paths at the top and separates inspection, export, and downstream steps.

## Documentation Map

- [Getting started](https://chags1313.github.io/monomech/docs/getting-started.html)
- [Example notebooks](https://chags1313.github.io/monomech/docs/examples.html)
- [Outputs and files](https://chags1313.github.io/monomech/docs/outputs.html)
- [OpenSim stage guide](https://chags1313.github.io/monomech/docs/stages/opensim.html)
- [Publishing guide](https://chags1313.github.io/monomech/docs/PUBLISHING.html)

## OpenSim Workflow

```python
import monomech as mm

model_path = mm.get_builtin_osim_model("pose")
trial = mm.load_video("data/subject01.mp4")
run = trial.run_pipeline(export_csv=True, export_trc=True, output_dir="outputs/subject01")

scale = trial.run_opensim_scale(
    model_path=model_path,
    trc_path=run.trc_path,
)

ik = trial.run_opensim_ik(
    model_path=scale.scaled_model_path,
    trc_path=run.trc_path,
)

estimated_loads = mm.external.estimate_grf(
    pose3d=run.pose3d_global,
    body_mass_kg=75.0,
)

id_result = trial.run_opensim_id(
    model_path=scale.scaled_model_path,
    ik_path=ik.path,
    external_forces=estimated_loads,
)
```

OpenSim itself can be installed through conda, or you can opt into the PyPI-compatible `pyopensim` binding with `monomech[opensim]`.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest tests
mkdocs build --strict
python -m build
```

Run a real video smoke test:

```bash
python examples/run_video_smoke.py "path/to/video.mp4" --output-dir outputs/smoke
```

Add `--opensim` when OpenSim-compatible bindings are installed.

## Publishing

GitHub Actions builds distributions on every push to `main`. PyPI publishing is triggered by version tags such as:

```bash
git tag v0.15.1
git push origin v0.15.1
```

The PyPI project must have a matching Trusted Publisher configured for `chags1313/monomech` and `.github/workflows/publish.yml`.

## License

See [LICENSE](LICENSE).
