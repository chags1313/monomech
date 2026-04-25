# External Forces

`monomech` includes `ExternalLoadsSpec` for attaching OpenSim external loads files to inverse dynamics workflows.

```python
external_loads = mm.ExternalLoadsSpec(
    data_path="outputs/external_loads.sto",
    xml_path="outputs/ExternalLoads.xml",
)
```

## OpenSim ID

External loads are passed into inverse dynamics:

```python
id_result = trial.run_opensim_id(
    model_path="scaled_model.osim",
    ik_path="outputs/ik/subject01_ik.mot",
    external_forces=external_loads,
)
```

## Recommendation

Keep force definitions and generated OpenSim files in the same trial output folder. This makes it easier to audit which force assumptions were used for each ID result.
