# Examples

Examples should show the same public API documented elsewhere: `mm.load_video()`, `mm.load_trc()`, trial methods, result exports, and optional OpenSim stages.

## Minimal Video Example

```python
import monomech as mm

trial = mm.load_video("subject01.mp4")

pose2d = trial.estimate_pose2d()
pose3d_world = trial.estimate_pose3d_world()
pose3d_global = trial.estimate_pose3d_global()

pose3d_global.to_csv("outputs/subject01_global.csv")
pose3d_global.to_trc("outputs/subject01_global.trc", model_path="model.osim")
```

## Minimal Marker Example

```python
import monomech as mm

trial = mm.load_trc("walk.trc")
trial.clean_markers(cutoff_hz=6.0)
trial.to_trc("outputs/walk_clean.trc")
```

## Suggested Notebook Progression

1. Start with a single video and inspect each result as a DataFrame.
2. Export CSV files and confirm the coordinate values make sense.
3. Export TRC and inspect marker names against your OpenSim model.
4. Run OpenSim scale and IK.
5. Add external loads and inverse dynamics only after IK results look reasonable.

## Good Example Hygiene

- Keep raw data paths at the top of the notebook.
- Keep one output directory per subject or trial.
- Save intermediate CSV files while tuning parameters.
- Record smoothing, gap-filling, and OpenSim config values in notebook text.
