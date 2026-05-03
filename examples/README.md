# monomech Example Notebooks

These notebooks are practical starting points for common workflows:

- `video_to_trc_quickstart.ipynb` uses `mm.estimate_pose()`, `mm.smooth()`, and `mm.gap_fill()` to convert a single-camera video into pose outputs and a TRC file.
- `marker_trc_cleanup.ipynb` loads an existing TRC, summarizes marker quality, cleans it with the top-level API, and exports a new TRC.
- `opensim_scale_ik_template.ipynb` shows `mm.run_scaling()` and `mm.run_ik()` once you have compatible pose or marker data.
- `video_to_inverse_dynamics_pipeline.ipynb` walks from video to OpenSim scale, IK, external loads, ID, and `mm.animate()`.
- `run_video_smoke.py` runs a repeatable command-line video smoke test and can optionally include OpenSim scale, IK, and ID through the high-level API.

Open a notebook, edit the paths in the first code cell, then run one section at a time.

The full video-to-inverse-dynamics notebook is meant to produce these review checkpoints:

- 2D landmarks over the source video frame.
- Root-centered 3D pose for early body-shape checks.
- Global 3D pose after PnP placement and floor alignment.
- Key IK angle plots for hip, knee, ankle, trunk, and pelvis checks.
- Estimated external-load traces before inverse dynamics.
- Key ID force and moment traces for the main kinetic checks.
- A synchronized Three.js viewer with model motion, markers, force arrows, IK plots, and ID plots.
