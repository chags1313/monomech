"""Stage result containers with dataframe- and notebook-friendly helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .types import ExternalForceSpec, PoseSequence2D, PoseSequence3D


@dataclass(slots=True)
class StageResult:
    stage: str
    df: pd.DataFrame
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    figures: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Path] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if "df" not in self.tables:
            self.tables = {"df": self.df, **self.tables}

    def table(self, name: str = "df") -> pd.DataFrame:
        if name == "df":
            return self.df
        if name not in self.tables:
            raise KeyError(f"Unknown table '{name}'. Available: {sorted(self.tables)}")
        return self.tables[name]

    def head(self, n: int = 5, table: str = "df") -> pd.DataFrame:
        return self.table(table).head(n)

    def add_artifact(self, name: str, path: str | Path) -> Path:
        resolved = Path(path)
        self.artifacts[name] = resolved
        return resolved

    def summary(self) -> pd.DataFrame:
        return self.tables.get("summary", self.df.head(0))


@dataclass(slots=True)
class Pose2DResult(StageResult):
    sequence: PoseSequence2D | None = None


@dataclass(slots=True)
class World3DResult(StageResult):
    sequence: PoseSequence3D | None = None


@dataclass(slots=True)
class PnPResult(StageResult):
    sequence: PoseSequence3D | None = None


@dataclass(slots=True)
class GlobalPoseResult(StageResult):
    sequence: PoseSequence3D | None = None


@dataclass(slots=True)
class ForceSetResult(StageResult):
    specs: list[Any] = field(default_factory=list)
    resolved_specs: list[ExternalForceSpec] = field(default_factory=list)

    def to_opensim_specs(self) -> list[ExternalForceSpec]:
        return list(self.resolved_specs)


@dataclass(slots=True)
class IKResult(StageResult):
    motion_path: Path | None = None


@dataclass(slots=True)
class IDResult(StageResult):
    storage_path: Path | None = None


@dataclass(slots=True)
class PipelineRunResult:
    trial: Any
    pose2d: Pose2DResult | None = None
    world3d: World3DResult | None = None
    pnp: PnPResult | None = None
    global_pose: GlobalPoseResult | None = None
    forces: ForceSetResult | None = None
    ik: IKResult | None = None
    id: IDResult | None = None
    artifacts: dict[str, Path] = field(default_factory=dict)

    def available_stages(self) -> list[str]:
        stages = []
        for name in ["pose2d", "world3d", "pnp", "global_pose", "forces", "ik", "id"]:
            if getattr(self, name) is not None:
                stages.append(name)
        return stages

    def by_stage(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.available_stages()}

    def stage(self, name: str) -> Any:
        value = getattr(self, name)
        if value is None:
            raise KeyError(f"Stage '{name}' is unavailable. Available: {self.available_stages()}")
        return value
