# Outputs and files

Each stage returns a result object with a consistent shape:

- `df` — primary DataFrame
- `tables` — named DataFrames
- `artifacts` — files written to disk
- `meta` — metadata and processing settings
- `figures` — notebook-ready figures when available

## Standard file philosophy

Whenever possible, `monomech` writes both:

- a **biomechanics-native file** for downstream tooling
- a **CSV copy** for direct inspection and analysis

## Typical outputs by stage

## `pose2d`
- `pose2d.csv`
- `pose2d.parquet`

## `world3d`
- `world3d.csv`
- `world3d.parquet`

## `pnp`
- `pnp_camera_pose.csv`
- `pnp_reprojection.csv`

## `global_pose`
- `global_pose.csv`
- `global_pose.parquet`
- `global_pose.trc`

## `forces`
- `external_loads.csv`
- `external_loads.sto`
- `ExternalLoads.xml`

## `opensim.run_ik`
- `global_markers.trc`
- `global_markers.csv`
- `Setup_Scale.xml`
- `scale_measurements.csv`
- `scaled.osim`
- `Setup_IK.xml`
- `ik.mot`
- `ik.csv`

## `opensim.run_id`
- `external_loads.sto`
- `external_loads.csv`
- `ExternalLoads.xml`
- `id.sto`
- `id.csv`

## Recommended folder layout

```text
outputs/
  subject01/
    pose2d.csv
    world3d.csv
    pnp_camera_pose.csv
    global_pose.csv
    global_pose.trc
    global_markers.trc
    global_markers.csv
    Setup_Scale.xml
    scale_measurements.csv
    scaled.osim
    Setup_IK.xml
    ik.mot
    ik.csv
    external_loads.sto
    external_loads.csv
    ExternalLoads.xml
    id.sto
    id.csv
```
