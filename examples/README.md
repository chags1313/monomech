# monomech Example Notebooks

These notebooks are practical starting points for common workflows:

- `video_to_trc_quickstart.ipynb` converts a single-camera video into pose outputs and a TRC file.
- `marker_trc_cleanup.ipynb` loads an existing TRC, summarizes marker quality, cleans it, and exports a new TRC.
- `opensim_scale_ik_template.ipynb` shows the OpenSim scale and inverse kinematics handoff once you have a compatible TRC.
- `video_to_inverse_dynamics_pipeline.ipynb` walks from video to TRC, OpenSim scale, IK, estimated external loads, and inverse dynamics.
- `run_video_smoke.py` runs a repeatable command-line video smoke test and can optionally include OpenSim scale, IK, and ID.

Open a notebook, edit the paths in the first code cell, then run one section at a time.
