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
- Review GLB meshes, markers, external-force arrows, IK traces, and ID traces in a Three.js HTML viewer.
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
run = mm.video_to_trc(video_path, output_dir=output_dir)

print(run.csv_paths)
print(run.trc_path)
```

## Notebook-First Workflow

The high-level API is designed to read like the analysis steps in a notebook:

```python
import monomech as mm

pose = mm.estimate_pose(
    "data/curl.mp4",
    root_centered=False,
    floored=True,
)

pose = mm.smooth(pose, cutoff_hz=6.0)
pose = mm.gap_fill(pose, max_gap_frames=12)

pose.vis_2d(frame=100)
pose.vis_3d(frame=100)

scaled_model = mm.run_scaling(pose, model="pose", output_dir="outputs/curl/scale")
ik = mm.run_ik(scaled_model, output_dir="outputs/curl/ik")

dumbbell = mm.load(type="carried", body="hand_r", mass_kg=10.0)
grf = mm.estimate_grf(pose, body_mass_kg=82.0)
forces = mm.external_forces(loads=[dumbbell, *grf])

id_result = mm.run_id(
    ik=ik,
    external_forces=forces,
    output_dir="outputs/curl/id",
)

ik.plot()
id_result.plot()

animation = mm.animate(
    ik=ik,
    id=id_result,
    external_loads_path=id_result.metadata["external_loads_mot_path"],
    output_dir="outputs/curl/visualizer",
)
animation.show()
```

For batch scripts, use the one-call aliases:

```python
result = mm.video_pipeline(
    "data/curl.mp4",
    model_path=mm.get_builtin_osim_model("pose"),
    output_dir="outputs/curl",
)

result.display()
```

## Full Pipeline: Video To Inverse Dynamics

```python
import monomech as mm

result = mm.video_to_inverse_dynamics(
    "data/subject01.mp4",
    model_path="models/subject01_scaled.osim",
    output_dir="outputs/subject01",
    body_mass_kg=75.0,
)

print(result.trc_path)
print(result.ik.path)
print(result.id.path)
print(result.visualizer.html_path)
result.display()
```

If you already have marker data in a TRC file, start at OpenSim:

```python
result = mm.trc_to_inverse_dynamics(
    "outputs/subject01/subject01.trc",
    model_path="models/subject01_scaled.osim",
    output_dir="outputs/subject01/opensim",
    external_forces=None,
)

print(result.ik.path)
print(result.id.path)
```

Export the IK and ID run to one portable animation file:

```python
animation = mm.save_opensim_animation(
    osim_path="models/subject01_scaled.osim",
    mot_path=result.ik.path,
    id_path=result.id.path,
    out_glb_path="outputs/subject01/animation/subject01_ik_id.glb",
    stride=2,
    decimate_target_reduction=0.35,
)

print(animation.glb_path)
```

Create a notebook-friendly Three.js dashboard with the animated model, marker fallback, force arrows, IK plots, and ID plots:

```python
viewer = mm.save_opensim_visualizer(
    "outputs/subject01/animation/ik_id_viewer.html",
    osim_path="models/subject01_scaled.osim",
    ik_path=result.ik.path,
    id_path=result.id.path,
    external_loads_path=result.id.metadata["external_loads_mot_path"],
    glb_path=animation.glb_path,
)

viewer
```

The dashboard is a standalone HTML file, so it works in notebooks, local browsers, and GitHub Pages. When `glb_path` is provided, the GLB is embedded so the animated mesh loads immediately. The online visualizer starts empty and includes an **Upload GLB** control, which lets a reader drag in their own exported model without sending the file anywhere.

For a carried object plus estimated ground-reaction forces:

```python
dumbbell = mm.external.carried_load(
    mass_kg=12.5,
    applied_to_body="radius_r",
    point=(0.0, -0.2, 0.0),
    name="right_dumbbell",
)

result = mm.video_to_inverse_dynamics(
    "data/curl.mp4",
    model_path=mm.get_builtin_osim_model("pose"),
    output_dir="outputs/curl",
    body_mass_kg=82.0,
    external_forces=mm.external.with_estimated_grf(dumbbell),
)
```

The GitHub Pages site includes an online GLB visualizer for quick review: [chags1313.github.io/monomech/visualizer/](https://chags1313.github.io/monomech/visualizer/).

Geometry note: the default full-body geometry is packaged with `monomech`, so most users do not need to pass `geom_dir`. Pass `geom_dir` only when using a different OpenSim model or custom mesh folder. If your model came from a macOS-created zip, avoid the `__MACOSX` folder because it usually contains only tiny `._*.vtp` metadata files, not usable meshes.

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
- [Online GLB visualizer](https://chags1313.github.io/monomech/visualizer/)
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

GitHub Actions builds distributions on every push to `main`. PyPI publishing goes directly to PyPI through trusted publishing and is triggered by version tags such as:

```bash
git tag v0.15.10
git push origin v0.15.10
```

The publish workflow can also be run manually from GitHub Actions with the `publish` input set to `true`.

## License

See [LICENSE](LICENSE).
