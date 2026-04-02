"""CSV and parquet export helpers."""

from __future__ import annotations

from pathlib import Path

from ..types import TrialResult
from ..utils.files import ensure_dir


def export_trial_csv_bundle(trial: TrialResult, output_dir: str | Path) -> dict[str, Path]:
    out = ensure_dir(output_dir)
    written: dict[str, Path] = {}

    if trial.pose2d is not None:
        path = out / f"{trial.name}_pose2d.csv"
        trial.pose2d.to_dataframe().to_csv(path, index=False)
        written["pose2d_csv"] = path
    if trial.world_pose is not None:
        path = out / f"{trial.name}_world_pose.csv"
        trial.world_pose.to_dataframe().to_csv(path, index=False)
        written["world_pose_csv"] = path
    if trial.pnp_pose is not None:
        path = out / f"{trial.name}_pnp_pose.csv"
        trial.pnp_pose.to_dataframe().to_csv(path, index=False)
        written["pnp_pose_csv"] = path
    if trial.global_pose is not None:
        path = out / f"{trial.name}_global_pose.csv"
        trial.global_pose.to_dataframe().to_csv(path, index=False)
        written["global_pose_csv"] = path

    trial.artifacts.update(written)
    return written


def export_stage_tables(stage_result, output_dir: str | Path) -> dict[str, Path]:
    out = ensure_dir(output_dir)
    written: dict[str, Path] = {}
    for name, df in stage_result.tables.items():
        if df is None:
            continue
        csv_path = out / f"{stage_result.stage}_{name}.csv"
        df.to_csv(csv_path, index=False)
        written[f"{name}_csv"] = csv_path
        parquet_path = out / f"{stage_result.stage}_{name}.parquet"
        try:
            df.to_parquet(parquet_path, index=False)
            written[f"{name}_parquet"] = parquet_path
        except Exception:
            pass
    stage_result.artifacts.update(written)
    return written
