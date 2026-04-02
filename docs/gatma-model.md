# GATMA model guide

`monomech` includes a GATMA-specific OpenSim preset shaped around the exact-model workflow from your original notebook.

## What the preset does

- resolves semantic aliases like `right_foot` and `left_shank` to model bodies
- writes marker and landmark exports suitable for GATMA processing
- generates scale measurements and scale setup files
- writes IK and ID setup files plus CSV mirrors

## Semantic aliases

Typical aliases include:

- `right_foot` → `calcn_r`
- `left_foot` → `calcn_l`
- `right_shank` → `tibia_r`
- `left_shank` → `tibia_l`
- `right_thigh` → `femur_r`
- `left_thigh` → `femur_l`
- `pelvis` → `pelvis`
- `trunk` → `torso`
- `right_hand` → `hand_r`
- `left_hand` → `hand_l`

## Typical GATMA flow

```python
trial = mm.Trial.from_video("subject01.mp4")
pose2d = mm.pose2d.process(trial)
world3d = mm.world3d.process(trial, pose2d=pose2d)
pnp = mm.pnp.solve(trial, pose2d=pose2d, world3d=world3d)
global_pose = mm.global_pose.estimate(trial, pose2d=pose2d, world3d=world3d, pnp=pnp)

ik = mm.opensim.run_ik(
    trial,
    global_pose=global_pose,
    model_path="GATMA_Model.osim",
)
```
