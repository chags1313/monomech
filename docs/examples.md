# Examples

The example notebooks are designed to be read top to bottom. Each notebook keeps input paths near the top, exports into a dedicated output folder, and pauses after important stages so you can inspect the data before continuing.

## Notebooks

| Notebook | Use it when | Main outputs |
| --- | --- | --- |
| [`video_to_trc_quickstart.ipynb`](https://github.com/chags1313/monomech/blob/main/examples/video_to_trc_quickstart.ipynb) | You have a single-camera video and want CSV/TRC exports. | pose CSV files, global TRC |
| [`marker_trc_cleanup.ipynb`](https://github.com/chags1313/monomech/blob/main/examples/marker_trc_cleanup.ipynb) | You already have a TRC file and want a cleaned version. | marker summary, cleaned TRC |
| [`opensim_scale_ik_template.ipynb`](https://github.com/chags1313/monomech/blob/main/examples/opensim_scale_ik_template.ipynb) | You have a TRC and want to set up OpenSim scale and IK. | scale setup, scaled model, IK motion |
| [`video_to_inverse_dynamics_pipeline.ipynb`](https://github.com/chags1313/monomech/blob/main/examples/video_to_inverse_dynamics_pipeline.ipynb) | You want a full video -> TRC -> scale -> IK -> external loads -> ID walkthrough. | pose outputs, OpenSim files, estimated loads, ID storage |
| [`run_video_smoke.py`](https://github.com/chags1313/monomech/blob/main/examples/run_video_smoke.py) | You want a repeatable command-line test for a real video. | JSON report, CSV, TRC, optional OpenSim outputs |

## Suggested Order

<div class="mono-path" markdown>
<div class="mono-step" markdown>
**Run the import cell**

Confirm the environment imports `monomech` before pointing at large data files.
</div>
<div class="mono-step" markdown>
**Set paths once**

Edit the `DATA_DIR`, input file, and `OUTPUT_DIR` variables near the top of each notebook.
</div>
<div class="mono-step" markdown>
**Inspect before export**

Use summaries and DataFrame previews before writing CSV or TRC files.
</div>
<div class="mono-step" markdown>
**Move downstream slowly**

Only run OpenSim after marker names, units, and time ranges look sensible.
</div>
</div>

## Full Video To ID Example

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
```

## Command-Line Smoke Test

```bash
python examples/run_video_smoke.py "data/subject01.mp4" --output-dir outputs/subject01_smoke
```

Run OpenSim too when the bindings are installed:

```bash
python examples/run_video_smoke.py "data/subject01.mp4" --output-dir outputs/subject01_smoke --opensim
```

## Minimal Video Example

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

## Minimal Marker Example

```python
from pathlib import Path
import monomech as mm

trc_path = Path("data/walk.trc")
output_dir = Path("outputs/walk")
output_dir.mkdir(parents=True, exist_ok=True)

trial = mm.load_trc(trc_path)
print(trial.summary())

trial.clean_markers(cutoff_hz=6.0)
trial.to_trc(output_dir / "walk_clean.trc")
```

## Good Notebook Hygiene

- Keep raw input files in `data/` and generated files in `outputs/`.
- Save intermediate CSV files while tuning pose, smoothing, or marker mapping.
- Record the exact install command and package version in the first notebook cell.
- Use one notebook per subject when parameter choices differ between trials.
- Keep OpenSim scale, IK, and ID sections separate so failures are easier to debug.
