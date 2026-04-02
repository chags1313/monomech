"""Optional import helpers."""

from __future__ import annotations

import importlib

from ..exceptions import OptionalDependencyError


def import_optional(module_name: str, extra_name: str | None = None):
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        hint = f" Install the optional dependency for '{extra_name}'." if extra_name else ""
        raise OptionalDependencyError(
            f"Missing optional dependency: {module_name}.{hint}"
        ) from exc
