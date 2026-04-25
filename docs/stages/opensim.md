# OpenSim

OpenSim helpers are available as methods on `VideoTrial` and `MarkerTrial`.

## Scale

```python
scale = trial.run_opensim_scale(
    model_path="model.osim",
    trc_path="outputs/subject01_global.trc",
    output_dir="outputs/subject01/scale",
)
```

## Inverse Kinematics

```python
ik = trial.run_opensim_ik(
    model_path=scale.scaled_model_path,
    trc_path="outputs/subject01_global.trc",
    output_dir="outputs/subject01/ik",
)
```

## Inverse Dynamics

```python
id_result = trial.run_opensim_id(
    model_path=scale.scaled_model_path,
    ik_path=ik.mot_path,
    external_forces=None,
    output_dir="outputs/subject01/id",
)
```

## Requirements

Install OpenSim-compatible Python bindings before calling OpenSim methods.

Options include:

- conda OpenSim distribution exposing an `opensim` Python module
- PyPI-compatible `pyopensim` through `python -m pip install "monomech[opensim]"`

## Built-In Models

```python
model_path = mm.get_builtin_osim_model("pose")
```

Use `mm.list_builtin_osim_models()` to see model aliases.
