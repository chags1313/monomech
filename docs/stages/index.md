# Stage Overview

`monomech` keeps each major operation explicit. You can run only the stage you need, inspect its output, and continue later.

## Video-First Path

```mermaid
flowchart LR
    video["Video file"] --> load["mm.load_video"]
    load --> pose2d["estimate_pose2d"]
    pose2d --> world["estimate_pose3d_world"]
    world --> global["estimate_pose3d_global"]
    global --> csv["CSV export"]
    global --> trc["TRC export"]
    trc --> opensim["OpenSim scale / IK / ID"]
```

## Marker-First Path

```mermaid
flowchart LR
    trc["TRC file"] --> load["mm.load_trc"]
    load --> clean["gap fill + smooth"]
    clean --> export["TRC / CSV export"]
    export --> opensim["OpenSim scale / IK / ID"]
```

## Main APIs

| Stage | API | Notes |
| --- | --- | --- |
| Load video | `mm.load_video(path)` | Creates a `VideoTrial`. |
| Estimate 2D pose | `trial.estimate_pose2d()` | Requires `monomech[pose]`. |
| Estimate world pose | `trial.estimate_pose3d_world()` | Uses pose results from the video stage. |
| Estimate global pose | `trial.estimate_pose3d_global()` | Produces global coordinates suitable for export. |
| Load markers | `mm.load_trc(path)` | Creates a `MarkerTrial`. |
| Clean markers | `trial.clean_markers()` | Gap fill and smooth marker trajectories. |
| OpenSim | `trial.run_opensim_*()` | Requires OpenSim-compatible bindings. |
