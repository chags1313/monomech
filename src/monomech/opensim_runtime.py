from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace


_REQUIRED_TOOL_NAMES = (
    "ScaleTool",
    "InverseKinematicsTool",
    "InverseDynamicsTool",
    "Model",
)


class _OpenSimProxy:
    """
    Normalize OpenSim-compatible bindings so the rest of MonoMech can use:
        osim.ScaleTool()
        osim.InverseKinematicsTool()
        osim.InverseDynamicsTool()
        osim.Model()
    regardless of whether those classes live at the package top level
    or under a tools submodule.
    """

    def __init__(self, base_module, tools_module=None):
        self._base = base_module
        self._tools = tools_module

    def __getattr__(self, name):
        if hasattr(self._base, name):
            return getattr(self._base, name)
        if self._tools is not None and hasattr(self._tools, name):
            return getattr(self._tools, name)
        raise AttributeError(f"{self._base.__name__} has no attribute '{name}'")

    @property
    def __name__(self):
        return getattr(self._base, "__name__", type(self._base).__name__)

    @property
    def __version__(self):
        return getattr(self._base, "__version__", None)

    @property
    def __opensim_version__(self):
        return getattr(self._base, "__opensim_version__", None)


def _import_optional(module_name: str):
    try:
        return importlib.import_module(module_name)
    except Exception:
        return None


def _build_pyopensim_proxy():
    import pyopensim as base

    # Try likely tool namespaces.
    tools = (
        _import_optional("pyopensim.tools")
        or _import_optional("pyopensim.opensim.tools")
        or _import_optional("pyopensim.Tools")
    )

    proxy = _OpenSimProxy(base, tools)

    missing = [name for name in _REQUIRED_TOOL_NAMES if not hasattr(proxy, name)]
    if missing:
        raise ImportError(
            "pyopensim imported, but required OpenSim tool classes were not found. "
            f"Missing: {missing}"
        )

    return proxy


def _build_official_opensim_proxy():
    import opensim as base
    proxy = _OpenSimProxy(base, None)

    missing = [name for name in _REQUIRED_TOOL_NAMES if not hasattr(proxy, name)]
    if missing:
        raise ImportError(
            "opensim imported, but required OpenSim tool classes were not found. "
            f"Missing: {missing}"
        )

    return proxy


def require_opensim():
    errors: list[str] = []

    try:
        return _build_pyopensim_proxy()
    except Exception as exc:
        errors.append(f"pyopensim failed: {exc}")

    try:
        return _build_official_opensim_proxy()
    except Exception as exc:
        errors.append(f"opensim failed: {exc}")

    raise ImportError(
        "MonoMech requires OpenSim-compatible Python bindings with tool support.\n\n"
        f"Python: {sys.executable}\n"
        + "\n".join(errors)
        + "\n\n"
        "Expected tool classes:\n"
        "  ScaleTool, InverseKinematicsTool, InverseDynamicsTool, Model"
    )