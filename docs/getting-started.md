# Getting started

## 1. Install the package

From PyPI:

```bash
python -m pip install monomech
```

For local development from the repository:

```bash
python -m pip install -e .
python -m pip install -e ".[dev]"
```

## 2. Open a notebook or Python session

`monomech` is designed to feel natural in Jupyter notebooks.

```python
import monomech as mm
```

## 3. Create a trial from a video

```python
trial = mm.Trial.from_video("subject01.mp4")
```

## 4. Run individual stages

```python
pose2d = mm.pose2d.process(trial)
world3d = mm.world3d.process(trial, pose2d=pose2d)
pnp = mm.pnp.solve(trial, pose2d=pose2d, world3d=world3d)
global_pose = mm.global_pose.estimate(trial, pose2d=pose2d, world3d=world3d, pnp=pnp)
```

## 5. Inspect outputs as tables

```python
pose2d.df.head()
pose2d.tables["landmarks_long"].head()
world3d.tables["world3d_long"].head()
pnp.tables["camera_pose"].head()
global_pose.tables["contacts"].head()
```

## 6. Use the full wrapper when desired

```python
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
```

## 7. Move into OpenSim

```python
ik = mm.opensim.run_ik(
    trial,
    global_pose=global_pose,
    model_path="GATMA_Model.osim",
)
```

## 8. Add external forces and inverse dynamics

```python
force_set = mm.ForceSet([
    mm.ExternalForce.constant(
        name="right_grf",
        target="right_foot",
        magnitude=900.0,
        direction=(0.0, 1.0, 0.0),
        point="right_ankle",
    )
])

forces = mm.forces.build(trial, global_pose=global_pose, force_set=force_set)
id_result = mm.opensim.run_id(
    trial,
    ik=ik,
    forces=forces,
    model_path="GATMA_Model.osim",
)
```
