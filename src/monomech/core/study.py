from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..utils import ensure_dir


@dataclass(slots=True)
class BatchRun:
    trials: list
    outputs: list

    def summary_df(self) -> pd.DataFrame:
        rows = []
        for trial, output in zip(self.trials, self.outputs):
            rows.append(
                {
                    "trial": trial.name,
                    "has_pose2d": output.pose2d is not None,
                    "has_pose3d_world": output.pose3d_world is not None,
                    "has_pose3d_global": output.pose3d_global is not None,
                    "trc_path": None if output.trc_path is None else str(output.trc_path),
                }
            )
        return pd.DataFrame(rows)


@dataclass(slots=True)
class Study:
    trials: list = field(default_factory=list)

    def run_pose_pipeline(self, *, output_dir: str | Path = "outputs/batch") -> BatchRun:
        out = ensure_dir(output_dir)
        outputs = []
        for trial in self.trials:
            outputs.append(
                trial.run_pipeline(
                    pose2d=True,
                    pose3d_world=True,
                    pose3d_global=True,
                    export_csv=True,
                    export_trc=True,
                    output_dir=out / trial.name,
                )
            )
        return BatchRun(trials=self.trials, outputs=outputs)
