# OpenSim

OpenSim helpers are available as methods on `VideoTrial` and `MarkerTrial`. The helpers write setup files, run OpenSim tools, read the outputs back into `StorageResult` objects, and keep useful paths in result metadata.

## Requirements

Install OpenSim-compatible Python bindings before calling OpenSim methods.

Options include:

- conda OpenSim distribution exposing an `opensim` Python module
- PyPI-compatible `pyopensim` through `python -m pip install "monomech[opensim]"`

## Built-In Models

```python
import monomech as mm

model_path = mm.get_builtin_osim_model("pose")
print(mm.list_builtin_osim_models())
```

By default, bundled models are copied without mesh display geometry. This avoids missing `.vtp` visualization warnings during command-line runs. If you want the original model references for a GUI workflow, use:

```python
model_path = mm.get_builtin_osim_model("pose", include_geometry=True)
```

## Scale

```python
scale = trial.run_opensim_scale(
    model_path=model_path,
    trc_path="outputs/subject01/subject01_global.trc",
    output_dir="outputs/subject01/scale",
)

print(scale.scaled_model_path)
print(scale.setup_xml_path)
```

Use `start_time` and `end_time` on the trial method when you want to scale from a stable subsection:

```python
scale = trial.run_opensim_scale(
    model_path=model_path,
    trc_path=trc_path,
    start_time=0.25,
    end_time=1.25,
)
```

## Inverse Kinematics

```python
ik = trial.run_opensim_ik(
    model_path=scale.scaled_model_path,
    trc_path="outputs/subject01/subject01_global.trc",
    output_dir="outputs/subject01/ik",
)

print(ik.path)
display(ik.to_dataframe().head())
print(ik.metadata["marker_error_summary"])
```

Add marker weights when some markers should matter more:

```python
from monomech import OpenSimIKConfig

ik = trial.run_opensim_ik(
    model_path=scale.scaled_model_path,
    trc_path=trc_path,
    config=OpenSimIKConfig(
        marker_weights={
            "right_ankle": 5.0,
            "left_ankle": 5.0,
        },
    ),
)
```

## External Loads

Inverse dynamics can run with no external loads for a setup check, but meaningful kinetics usually need measured or estimated external forces.

```python
estimated_loads = mm.external.estimate_grf(
    pose3d=pose3d_global,
    body_mass_kg=75.0,
)
```

See [External loads and forces](forces.md) for measured force plates, manual loads, carried loads, estimated GRF, and troubleshooting.

## Inverse Dynamics

```python
id_result = trial.run_opensim_id(
    model_path=scale.scaled_model_path,
    ik_path=ik.path,
    external_forces=estimated_loads,
    output_dir="outputs/subject01/id",
)

print(id_result.path)
display(id_result.to_dataframe().head())
```

Generated external-load files are reported in metadata:

```python
print(id_result.metadata["external_loads_xml_path"])
print(id_result.metadata["external_loads_mot_path"])
```

## Preflight And NaN Handling

OpenSim is sensitive to NaNs and infinite values. The helpers run automatic preflight fixes by default:

| Stage | Default check | Output |
| --- | --- | --- |
| Scale | TRC marker values must be finite. NaNs are interpolated. | `*_opensim_ready.trc` when needed |
| IK | TRC marker values must be finite. NaNs are interpolated. | `*_opensim_ready.trc` when needed |
| ID | IK coordinate values must be finite. NaNs are interpolated. | `*_coordinates_opensim_ready.mot` when needed |
| External loads | Forces and points are numeric and aligned to IK time. | `*_external_loads.mot`, `*_ExternalLoads.xml` |

Inspect preflight metadata:

```python
print(ik.metadata["preflight"])
print(ik.metadata["marker_error_summary"])
print(id_result.metadata["coordinate_preflight"])
```

## Quiet Logs

OpenSim can print a line per frame during IK. `monomech` runs OpenSim tools in quiet mode by default and writes stage logs next to the outputs.

```python
print(scale.metadata["log_path"])
print(ik.metadata["log_path"])
print(id_result.metadata["log_path"])
```

Set `quiet=False` when you want OpenSim output in the console:

```python
from monomech import OpenSimIKConfig

ik = trial.run_opensim_ik(
    model_path=scale.scaled_model_path,
    trc_path=trc_path,
    config=OpenSimIKConfig(quiet=False),
)
```

Use strict mode when you want a failure instead of automatic interpolation:

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
    config=OpenSimIDConfig(sanitize_coordinates=False),
)
```

## Practical Checklist

<div class="mono-path" markdown>
<div class="mono-step" markdown>
**Check marker names**

Compare TRC marker names against the OpenSim model before scale and IK.
</div>
<div class="mono-step" markdown>
**Inspect missing data**

Read `metadata["preflight"]` and review any all-missing marker channels.
</div>
<div class="mono-step" markdown>
**Align force timing**

Make force data cover the same time range as the IK file when running inverse dynamics.
</div>
<div class="mono-step" markdown>
**Review signs and bodies**

Confirm force directions, point units, and `applied_to_body` before trusting kinetics.
</div>
</div>
