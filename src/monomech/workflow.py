"""Full-pipeline wrapper around the modular stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from . import forces as forces_module
from . import global_pose as global_pose_module
from . import pnp as pnp_module
from . import pose2d as pose2d_module
from . import world3d as world3d_module
from ._shared import ensure_trial, trial_result_from_global
from .config import PipelineConfig
from .io.tabular import export_stage_tables
from .opensim import run_id, run_ik
from .results import PipelineRunResult
from .utils.files import ensure_dir


@dataclass(slots=True)
class PipelineStages:
    pose2d: bool = True
    world3d: bool = True
    pnp: bool = True
    global_pose: bool = True
    forces: bool = False
    ik: bool = False
    id: bool = False


@dataclass(slots=True)
class FullPipeline:
    config: PipelineConfig = field(default_factory=PipelineConfig)
    stages: PipelineStages = field(default_factory=PipelineStages)

    def run(self, video_or_trial, *, output_dir: str | Path | None = None, force_set: forces_module.ForceSet | list[forces_module.ExternalForce] | None = None, segment_map: dict[str, str] | None = None) -> PipelineRunResult:
        trial = ensure_trial(video_or_trial)
        bundle = PipelineRunResult(trial=trial)

        if self.stages.pose2d or self.stages.world3d or self.stages.pnp or self.stages.global_pose:
            bundle.pose2d = pose2d_module.process(trial, config=self.config.pose)
        if self.stages.world3d or self.stages.pnp or self.stages.global_pose:
            bundle.world3d = world3d_module.process(trial, pose2d=bundle.pose2d, config=self.config.pose)
        if self.stages.pnp or self.stages.global_pose:
            bundle.pnp = pnp_module.solve(trial, pose2d=bundle.pose2d, world3d=bundle.world3d, config=self.config.pnp)
        if self.stages.global_pose:
            bundle.global_pose = global_pose_module.estimate(trial, pose2d=bundle.pose2d, world3d=bundle.world3d, pnp=bundle.pnp, config=self.config.global_pose)
        if self.stages.forces and force_set is not None and bundle.global_pose is not None:
            bundle.forces = forces_module.build(trial, global_pose=bundle.global_pose, force_set=force_set, segment_map=segment_map)
        if self.stages.ik:
            if bundle.global_pose is None:
                raise ValueError("IK requires the global_pose stage.")
            bundle.ik = run_ik(trial, global_pose=bundle.global_pose, model_path=self.config.opensim.model_path, config=self.config.opensim, output_dir=(Path(output_dir) / self.config.opensim.output_dirname) if output_dir is not None else None)
        if self.stages.id:
            if bundle.global_pose is None:
                raise ValueError("ID requires the global_pose stage.")
            if bundle.forces is None and force_set is not None:
                bundle.forces = forces_module.build(trial, global_pose=bundle.global_pose, force_set=force_set, segment_map=segment_map)
            bundle.id = run_id(trial, global_pose=bundle.global_pose, forces=bundle.forces, model_path=self.config.opensim.model_path, config=self.config.opensim, output_dir=(Path(output_dir) / self.config.opensim.output_dirname) if output_dir is not None else None)

        if output_dir is not None:
            out = ensure_dir(output_dir)
            for stage_name, result in bundle.by_stage().items():
                export_stage_tables(result, out / stage_name)
                for key, path in result.artifacts.items():
                    bundle.artifacts[f"{stage_name}_{key}"] = path
            if bundle.global_pose is not None:
                trial_result = trial_result_from_global(trial, bundle.global_pose.sequence)
                dashboard_path = trial_result.export_dashboard_html(out / f"{trial.name}_dashboard.html", coordinate_set="global")
                bundle.artifacts["dashboard_html"] = dashboard_path
        return bundle

    def run_many(self, videos: Iterable[str | Path], *, output_dir: str | Path | None = None, force_set: forces_module.ForceSet | list[forces_module.ExternalForce] | None = None, segment_map: dict[str, str] | None = None) -> list[PipelineRunResult]:
        outputs: list[PipelineRunResult] = []
        base_out = ensure_dir(output_dir) if output_dir is not None else None
        for video in videos:
            trial = ensure_trial(video)
            trial_out = base_out / trial.name if base_out is not None else None
            outputs.append(self.run(trial, output_dir=trial_out, force_set=force_set, segment_map=segment_map))
        return outputs
