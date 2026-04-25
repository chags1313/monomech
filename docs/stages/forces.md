# External Loads And Forces

External loads are the force inputs used by OpenSim inverse dynamics. In `monomech`, external loads are represented by `ExternalLoadsSpec` objects and are usually created through the `mm.external` factory.

Use this page when you want to run inverse dynamics with ground reaction forces, a carried load, or another force time series.

## What Inverse Dynamics Needs

Inverse dynamics combines:

- a scaled OpenSim model
- an IK coordinates file, usually `ik.path`
- optional external forces, passed as `external_forces=...`
- a valid time range shared by the IK coordinates and force data

`monomech` writes the OpenSim external-load `.mot` and `ExternalLoads.xml` files for you when you pass an `ExternalLoadsSpec` into `run_opensim_id()`.

## From A DataFrame

Use this path when you already have force plate data, pressure mat data, or another measured force table.

```python
import pandas as pd
import monomech as mm

df = pd.read_csv("data/right_force_plate.csv")

right_grf = mm.external.from_dataframe(
    df=df,
    applied_to_body="calcn_r",
    force_columns=("ground_force_vx", "ground_force_vy", "ground_force_vz"),
    point_columns=("ground_force_px", "ground_force_py", "ground_force_pz"),
    torque_columns=("ground_torque_x", "ground_torque_y", "ground_torque_z"),
    time_column="time",
    name="right_grf",
    force_expressed_in="/ground",
    point_expressed_in="/ground",
)
```

The `name` becomes the OpenSim column prefix, so keep it short and unique.

## From A CSV

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

## From Arrays

```python
right_grf = mm.external.from_timeseries(
    time=pose3d_global.time,
    force=force_xyz,
    point=center_of_pressure_xyz,
    applied_to_body="calcn_r",
    name="right_grf",
)
```

`force` and `point` must both have shape `(n_frames, 3)` and match the length of `time`.

## Manual Constant Load

Use a constant load for a simple carried object or setup check.

```python
manual_load = mm.external.constant_force(
    applied_to_body="hand_r",
    force=(0.0, -49.05, 0.0),
    point=(0.0, 0.0, 0.0),
    start_time=0.0,
    end_time=2.0,
    name="right_hand_load",
)
```

`force` is in Newtons. In this example, `49.05 N` is roughly a 5 kg object under gravity.

## Carried Load Shortcut

```python
bag_load = mm.external.carried_load(
    body="hand_r",
    mass_kg=5.0,
    start_time=0.0,
    end_time=2.0,
    name="right_hand_bag",
)
```

This is a convenience wrapper around `constant_force()` with a global downward force.

## Estimated Ground Reaction Forces

When measured forces are unavailable, `estimate_grf()` can create approximate vertical contact forces from global 3D pose foot landmarks.

```python
estimated_loads = mm.external.estimate_grf(
    pose3d=pose3d_global,
    body_mass_kg=75.0,
    sides=("left", "right"),
)
```

These loads are estimates, not a replacement for measured force plates. They are useful for examples, pipeline testing, and rough exploratory workflows.

## Run Inverse Dynamics

Pass one load or a list of loads:

```python
id_result = trial.run_opensim_id(
    model_path=scale.scaled_model_path,
    ik_path=ik.path,
    external_forces=estimated_loads,
    output_dir="outputs/subject01/id",
)

print(id_result.path)
print(id_result.metadata["external_loads_xml_path"])
print(id_result.metadata["external_loads_mot_path"])
```

## NaNs And Time Alignment

OpenSim tools generally expect finite numeric inputs. The `monomech` OpenSim helpers now run a preflight pass:

- TRC marker gaps are interpolated before scale and IK when `sanitize_marker_data=True`.
- IK coordinate NaNs are interpolated before inverse dynamics when `sanitize_coordinates=True`.
- External force values are resampled to IK time and non-finite values are filled with zero.
- Generated preflight paths and fill reports are stored in result metadata.

Disable the automatic fix when you want strict failure:

```python
from monomech import OpenSimIKConfig, OpenSimIDConfig

ik = trial.run_opensim_ik(
    model_path=scale.scaled_model_path,
    trc_path=trc_path,
    config=OpenSimIKConfig(sanitize_marker_data=False),
)

id_result = trial.run_opensim_id(
    model_path=scale.scaled_model_path,
    ik_path=ik.path,
    external_forces=estimated_loads,
    config=OpenSimIDConfig(sanitize_coordinates=False),
)
```

## Common Fixes

| Problem | Fix |
| --- | --- |
| Force data has a different sampling rate than IK | Pass the load to `run_opensim_id()`; it is resampled to IK time automatically. |
| Force data contains isolated NaNs | The generated external-load `.mot` fills non-finite values so OpenSim sees finite data. |
| TRC marker gaps break scale or IK | Use the default sanitizer, or clean the marker trial with `trial.clean_markers()` before export. |
| A marker channel is entirely missing | The sanitizer fills it with zero and reports it in metadata; inspect or remove that marker before trusting the result. |
| ID succeeds but forces look wrong | Check `applied_to_body`, `force_expressed_in`, `point_expressed_in`, units, signs, and center-of-pressure columns. |
