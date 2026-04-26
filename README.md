# monomech

[![CI](https://github.com/chags1313/monomech/actions/workflows/ci.yml/badge.svg)](https://github.com/chags1313/monomech/actions/workflows/ci.yml)
[![Docs](https://github.com/chags1313/monomech/actions/workflows/docs.yml/badge.svg)](https://github.com/chags1313/monomech/actions/workflows/docs.yml)
[![PyPI](https://img.shields.io/pypi/v/monomech.svg)](https://pypi.org/project/monomech/)
[![Python](https://img.shields.io/pypi/pyversions/monomech.svg)](https://pypi.org/project/monomech/)

`monomech` is a notebook-first Python library for single-camera biomechanics. It helps you move from video or marker data into inspectable pose results, OpenSim-ready TRC files, inverse kinematics, inverse dynamics, and analysis tables without hiding the intermediate steps.

Full documentation: [chags1313.github.io/monomech](https://chags1313.github.io/monomech/)

## Why Use It

- Start from a normal video or an existing TRC file.
- Export readable CSV and OpenSim-compatible TRC files.
- Run pose estimation, marker cleanup, scaling, inverse kinematics, and inverse dynamics as separate inspectable steps.
- Create OpenSim external loads from measured force data, arrays, carried loads, or estimated ground reaction forces.
- Export IK-driven OpenSim animations to a single portable GLB file.
- Keep OpenSim preflight checks on by default so NaNs and isolated gaps are fixed before IK and ID runs.
- Import the base package without installing heavy optional video or OpenSim dependencies.

## Install

```bash
python -m pip install monomech
```

Choose extras only when you need them:

| Workflow | Install command |
| --- | --- |
| Video pose estimation | `python -m pip install "monomech[pose]"` |
| OpenSim Python bindings | `python -m pip install "monomech[opensim]"` |
| OpenSim animation export | `python -m pip install "monomech[animation]"` |
| Notebooks and plots | `python -m pip install "monomech[notebook]"` |
| Everything optional | `python -m pip install "monomech[all]"` |

`monomech` supports Python 3.10 through 3.12.

## Quick Start: Video To TRC

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

Or run the common video export path in one call:

```python
run = trial.run_pipeline(
    export_csv=True,
    export_trc=True,
    output_dir=output_dir,
)

print(run.csv_paths)
print(run.trc_path)
```

## Full Pipeline: Video To Inverse Dynamics

```python
import monomech as mm

trial = mm.load_video("data/subject01.mp4")
run = trial.run_pipeline(export_csv=True, export_trc=True, output_dir="outputs/subject01")

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
print(id_result.metadata["external_loads_xml_path"])
```

Export the IK and ID run to one portable animation file:

```python
animation = mm.save_opensim_animation(
    osim_path=scale.scaled_model_path,
    mot_path=ik.path,
    id_path=id_result.path,
    out_glb_path="outputs/subject01/animation/subject01_ik_id.glb",
    stride=2,
    decimate_target_reduction=0.35,
)

print(animation.glb_path)
```

For measured force plates, build an external-load spec from your force table:

```python
right_grf = mm.external.from_csv(
    "data/right_force_plate.csv",
    applied_to_body="calcn_r",
    force_columns=("Fx", "Fy", "Fz"),
    point_columns=("Px", "Py", "Pz"),
    torque_columns=("Mx", "My", "Mz"),
    time_column="time",
    name="right_grf",
)
```

## OpenSim Reliability Defaults

OpenSim is strict about missing or non-finite values. The OpenSim helpers preflight inputs by default:

- TRC marker gaps are interpolated before scale and IK.
- IK coordinate NaNs are interpolated before inverse dynamics.
- External-load data is resampled to IK time and non-finite force values are filled with zero.
- Preflight reports and generated paths are stored in result metadata.

```python
print(ik.metadata["preflight"])
print(id_result.metadata["coordinate_preflight"])
```

## Example Notebooks

The `examples/` folder includes ready-to-edit notebooks:

- [`video_to_trc_quickstart.ipynb`](examples/video_to_trc_quickstart.ipynb) for video to CSV/TRC.
- [`marker_trc_cleanup.ipynb`](examples/marker_trc_cleanup.ipynb) for TRC inspection, gap filling, and smoothing.
- [`opensim_scale_ik_template.ipynb`](examples/opensim_scale_ik_template.ipynb) for OpenSim scale and IK setup.
- [`video_to_inverse_dynamics_pipeline.ipynb`](examples/video_to_inverse_dynamics_pipeline.ipynb) for video to IK/ID with external loads.
- [`run_video_smoke.py`](examples/run_video_smoke.py) for repeatable command-line checks on a real video.

## Documentation

- [Getting started](https://chags1313.github.io/monomech/getting-started/)
- [Example notebooks](https://chags1313.github.io/monomech/examples/)
- [External loads and forces](https://chags1313.github.io/monomech/stages/forces/)
- [OpenSim scale, IK, and ID](https://chags1313.github.io/monomech/stages/opensim/)
- [OpenSim animation export](https://chags1313.github.io/monomech/stages/animation/)
- [Full video-to-ID pipeline](https://chags1313.github.io/monomech/stages/full-pipeline/)
- [Outputs and files](https://chags1313.github.io/monomech/outputs/)

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

## License

See [LICENSE](LICENSE).
