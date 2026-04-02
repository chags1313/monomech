"""OpenSim namespace with lazy imports to avoid circular import during package init."""

from __future__ import annotations

__all__ = [
    "GATMA_PRESET",
    "OpenSimPipeline",
    "build_external_loads_bundle",
    "import_opensim",
    "infer_model_preset",
    "parse_model_marker_names",
    "run_id",
    "run_ik",
    "run_opensim_tool",
]


def __getattr__(name: str):
    if name in {"run_id", "run_ik"}:
        from .api import run_id, run_ik
        return {"run_id": run_id, "run_ik": run_ik}[name]
    if name in {"import_opensim", "run_opensim_tool"}:
        from .runtime import import_opensim, run_opensim_tool
        return {"import_opensim": import_opensim, "run_opensim_tool": run_opensim_tool}[name]
    if name == "build_external_loads_bundle":
        from .external_loads import build_external_loads_bundle
        return build_external_loads_bundle
    if name == "OpenSimPipeline":
        from .pipeline import OpenSimPipeline
        return OpenSimPipeline
    if name in {"GATMA_PRESET", "infer_model_preset", "parse_model_marker_names"}:
        from .presets import GATMA_PRESET, infer_model_preset, parse_model_marker_names
        return {
            "GATMA_PRESET": GATMA_PRESET,
            "infer_model_preset": infer_model_preset,
            "parse_model_marker_names": parse_model_marker_names,
        }[name]
    raise AttributeError(name)
