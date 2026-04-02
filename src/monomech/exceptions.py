"""Package-specific exceptions."""

class MonomechError(Exception):
    """Base error for monomech."""


class OptionalDependencyError(MonomechError):
    """Raised when an optional dependency is unavailable."""


class ProcessingError(MonomechError):
    """Raised when a processing stage fails."""


class OpenSimError(MonomechError):
    """Raised for OpenSim-related failures."""
