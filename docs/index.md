# monomech

`monomech` is a notebook-first monocular biomechanics library built around **explicit, inspectable stages** rather than a black-box pipeline.

It is designed for workflows where you want to:

- start from one video or many videos
- inspect **2D pose** in image space
- inspect **MediaPipe world landmarks** as root-centered **world3d**
- solve **PnP** from `pose2d + world3d`
- estimate **global pose** from `pose2d + world3d + pnp`
- define **semantic external forces** on body segments or exact OpenSim bodies
- export both **native biomechanics files** and easy-to-read **CSV tables**
- use **OpenSim** for scaling, inverse kinematics, and inverse dynamics

## Core ideas

### Modular stages
Each stage is a first-class API boundary. You can run one stage, inspect it, save it, compare it, and continue later.

### Notebook-first outputs
Every major stage returns result objects with DataFrames, artifacts, metadata, and visualization handles.

### Full-pipeline convenience
When you do want a single orchestrated run, `FullPipeline` wraps the same modular stages instead of hiding them.

## Stage map

- `pose2d` — image-space MediaPipe landmarks
- `world3d` — direct MediaPipe world landmarks, treated as root-centered 3D
- `pnp` — camera/root reconstruction from `pose2d + world3d`
- `global_pose` — floor-aligned global coordinates from `pose2d + world3d + pnp`
- `forces` — semantic or exact-body external loads
- `opensim.run_ik` — scale + IK helpers and exports
- `opensim.run_id` — external loads + inverse dynamics helpers and exports
- `FullPipeline` — wrapper around the same stage objects

## Quick example

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
```

## Where to go next

- [Getting started](getting-started.md)
- [Examples](examples.md)
- [Modular stages overview](stages/index.md)
- [Outputs and files](outputs.md)
- [GATMA model guide](gatma-model.md)
