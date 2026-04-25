# monomech

`monomech` is a **notebook-first, modular monocular biomechanics library** for turning video into inspectable kinematics, OpenSim-ready artifacts, and analysis-friendly tables.

It is designed around explicit stages:

- `pose2d` — MediaPipe image-space pose landmarks
- `world3d` — direct MediaPipe pose world landmarks, treated as root-centered 3D
- `pnp` — camera/root reconstruction from `pose2d + world3d`
- `global_pose` — floor-aligned global pose from `pose2d + world3d + pnp`
- `forces` — semantic external force specification with body and segment aliases
- `opensim.run_ik` — scaling and inverse kinematics helpers
- `opensim.run_id` — external loads and inverse dynamics helpers
- `FullPipeline` — a wrapper that orchestrates any combination of those stages

This repository is set up to be easy to use in three modes:

1. **Notebook exploration** — inspect every stage as DataFrames and inline figures.
2. **Scripted pipelines** — build reproducible analyses in Python scripts.
3. **GitHub + PyPI publishing** — publish through GitHub Actions with Trusted Publishing.

## Repository map

- `src/monomech/` — package source code
- `examples/` — runnable notebooks and scripts
- `tests/` — test suite
- `docs/` — setup, publishing, contributing, and workflow guides
- `.github/` — issue templates, PR template, and CI/CD workflows

Useful entry points:

- [Quick start](#quick-start)
- [Outputs by module](#outputs-by-module)
- [GitHub and release docs](#github-and-release-docs)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Documentation index](docs/README.md)
- GitHub Pages docs site: `https://your-github-username.github.io/monomech/`



## Documentation website

This repository is set up to publish a full documentation site with **GitHub Pages + MkDocs**.

Planned docs URL pattern:
- `https://your-github-username.github.io/monomech/`

After you put the repository on GitHub and enable Pages with the included workflow, the Markdown docs in `docs/` become a browsable site with navigation, search, and deep links.

## Installation

### From PyPI

```bash
python -m pip install monomech
```

For MediaPipe-based pose estimation:

```bash
python -m pip install "monomech[pose]"
```

For PyPI OpenSim-compatible bindings:

```bash
python -m pip install "monomech[opensim]"
```

For the full optional runtime stack:

```bash
python -m pip install "monomech[all]"
```

### For local development

```bash
python -m pip install -e .
python -m pip install -e ".[dev]"
```

### Runtime compatibility

This package currently targets **Python 3.11 and 3.12**.

## Quick start

### Modular workflow

```python
import monomech as mm

trial = mm.Trial.from_video("subject01.mp4")

pose2d = mm.pose2d.process(trial)
world3d = mm.world3d.process(trial, pose2d=pose2d)
pnp = mm.pnp.solve(trial, pose2d=pose2d, world3d=world3d)
global_pose = mm.global_pose.estimate(
    trial,
    pose2d=pose2d,
    world3d=world3d,
    pnp=pnp,
)

pose2d.tables["landmarks_long"].head()
world3d.tables["world3d_long"].head()
pnp.tables["camera_pose"].head()
global_pose.tables["contacts"].head()
```

### Full wrapper

```python
import monomech as mm

pipeline = mm.FullPipeline(
    stages=mm.PipelineStages(
        pose2d=True,
        world3d=True,
        pnp=True,
        global_pose=True,
        forces=False,
        ik=False,
        id=False,
    )
)

run = pipeline.run("subject01.mp4", output_dir="outputs/subject01")
run.global_pose.tables["summary"]
```

## GATMA exact-model support

This repository includes a **GATMA-specific OpenSim preset** based on your original workflow.

Highlights:

- semantic body aliases resolved to exact model bodies such as `calcn_r`, `tibia_r`, `femur_r`, `torso`, and `hand_r`
- landmark TRC export and model-marker TRC export
- auto-generated scale measurements
- scale, IK, and ID setup files
- CSV companions alongside biomechanics-native outputs whenever possible

## Force specification

You can target semantic segments or exact OpenSim bodies.

```python
import monomech as mm

force_set = mm.ForceSet([
    mm.ExternalForce.constant(
        name="right_grf",
        target="right_foot",
        magnitude=900.0,
        direction=(0.0, 1.0, 0.0),
        point="right_ankle",
    ),
    mm.ExternalForce.constant(
        name="left_hand_load",
        target="left_hand",
        magnitude=75.0,
        direction=(0.0, -1.0, 0.0),
        point="left_wrist",
    ),
])
```

## Outputs by module

Every stage returns a result object with:

- `df` — canonical primary DataFrame
- `tables` — named DataFrames for analysis
- `artifacts` — file paths written to disk
- `meta` — processing settings and metadata
- `figures` — notebook-ready visualization objects

### `pose2d`

Tables:
- `landmarks_long`
- `landmarks_wide`
- `visibility`
- `summary`

Typical artifacts:
- `pose2d.csv`
- `pose2d.parquet`

### `world3d`

Tables:
- `world3d_long`
- `world3d_wide`
- `segment_lengths`
- `visibility`
- `summary`

Typical artifacts:
- `world3d.csv`
- `world3d.parquet`

### `pnp`

Tables:
- `camera_pose`
- `reprojection`
- `pnp_long`
- `pnp_wide`
- `summary`

Typical artifacts:
- `pnp_camera_pose.csv`
- `pnp_reprojection.csv`

### `global_pose`

Tables:
- `global_pose_long`
- `global_pose_wide`
- `contacts`
- `floor`
- `root_trajectory`
- `summary`

Typical artifacts:
- `global_pose.csv`
- `global_pose.parquet`
- `global_pose.trc`

### `forces`

Tables:
- `forces_long`
- `forces_wide`
- `mapping`
- `summary`

Typical artifacts:
- `external_loads.csv`
- `external_loads.sto`
- `ExternalLoads.xml`

### `opensim.run_ik`

Tables:
- `coordinates`
- `model_markers`
- `summary`

Typical artifacts:
- landmark TRC
- model-marker TRC
- scale setup XML
- scale measurements CSV
- scaled model
- IK setup XML
- IK `.mot`
- IK `.csv`

### `opensim.run_id`

Tables:
- `generalized_forces`
- `external_loads`
- `summary`

Typical artifacts:
- ID setup XML
- ID `.sto`
- ID `.csv`

## Notebooks and examples

- `examples/monomech_modular_pipeline.ipynb` — modular stage-by-stage walkthrough
- `examples/monomech_gatma_exact_model.ipynb` — GATMA-specific workflow
- `examples/demo_workflow.py` — minimal scripted run

## GitHub and release docs

Start here if you are turning this into a public GitHub repository:

- [GitHub setup guide](docs/GITHUB_SETUP.md)
- [Publishing guide](docs/PUBLISHING.md)
- [Release guide](docs/RELEASING.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Troubleshooting and FAQ](docs/FAQ.md)

## Maintenance docs

- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

## Testing

```bash
pytest
```

## License

See [LICENSE](LICENSE).
