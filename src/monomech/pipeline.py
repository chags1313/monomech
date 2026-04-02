"""Backward-compatible pipeline API delegating to the modular wrapper."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .config import PipelineConfig
from .workflow import FullPipeline


@dataclass(slots=True)
class BatchResult:
    trials: list = field(default_factory=list)

    def by_name(self) -> dict[str, object]:
        return {trial.trial.name: trial for trial in self.trials}


@dataclass(slots=True)
class MonomechPipeline:
    config: PipelineConfig = field(default_factory=PipelineConfig)

    def run_video(self, video_path: str | Path, *, output_dir: str | Path | None = None, external_force_specs=None, run_opensim: bool | None = None):
        return FullPipeline(config=self.config).run(video_path, output_dir=output_dir)

    def run_many(self, videos: Iterable[str | Path], *, output_dir: str | Path | None = None, external_force_specs=None, run_opensim: bool | None = None) -> BatchResult:
        trials = FullPipeline(config=self.config).run_many(videos, output_dir=output_dir)
        return BatchResult(trials=trials)
