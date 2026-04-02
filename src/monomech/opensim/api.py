"""Notebook-first OpenSim stage wrappers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .._shared import ensure_trial, trial_result_from_global
from ..config import OpenSimConfig
from ..io.opensim import mot_to_dataframe, trc_to_dataframe
from ..results import ForceSetResult, IDResult, IKResult
from .pipeline import OpenSimPipeline


def run_ik(trial, *, global_pose, model_path: str | None, config: OpenSimConfig | None = None, output_dir: str | Path | None = None) -> IKResult:
    trial = ensure_trial(trial)
    cfg = config or OpenSimConfig(model_path=model_path, run_ik=True, run_id=False)
    if model_path is not None:
        cfg.model_path = model_path
    trial_result = trial_result_from_global(trial, global_pose.sequence if hasattr(global_pose, 'sequence') else global_pose)
    if output_dir is None:
        output_dir = Path.cwd() / f'{trial.name}_opensim'
    pipeline = OpenSimPipeline(cfg)
    artifacts = pipeline.run(trial_result, output_dir=output_dir, external_force_specs=None, coordinate_set=cfg.coordinate_set)
    mot_path = artifacts.get('ik_mot')
    coordinates_df = mot_to_dataframe(mot_path) if isinstance(mot_path, Path) else pd.DataFrame()
    marker_trc_df = trc_to_dataframe(artifacts['marker_trc']) if isinstance(artifacts.get('marker_trc'), Path) else pd.DataFrame()
    summary_df = pd.DataFrame([
        {
            'model_path': cfg.model_path,
            'model_preset': artifacts.get('model_preset'),
            'ik_executed': bool(artifacts.get('ik_run', {}).get('ok')) if isinstance(artifacts.get('ik_run'), dict) else False,
            'ik_motion_exists': bool(isinstance(mot_path, Path) and mot_path.exists()),
            'n_coordinate_rows': int(len(coordinates_df)),
            'n_marker_rows': int(len(marker_trc_df)),
            'n_ik_markers': int(artifacts.get('n_ik_markers') or 0),
        }
    ])
    result = IKResult(
        stage='ik',
        df=coordinates_df,
        tables={'coordinates': coordinates_df, 'model_markers': marker_trc_df, 'summary': summary_df},
        meta={'model_path': cfg.model_path, 'model_preset': artifacts.get('model_preset')},
        artifacts={k: v for k, v in artifacts.items() if isinstance(v, Path)},
        motion_path=mot_path if isinstance(mot_path, Path) else None,
    )
    return trial.register_stage('ik', result)


def run_id(trial, *, global_pose, forces: ForceSetResult | None, model_path: str | None, config: OpenSimConfig | None = None, output_dir: str | Path | None = None) -> IDResult:
    trial = ensure_trial(trial)
    if forces is None:
        raise ValueError('run_id requires a ForceSetResult.')
    cfg = config or OpenSimConfig(model_path=model_path, run_ik=True, run_id=True)
    if model_path is not None:
        cfg.model_path = model_path
    trial_result = trial_result_from_global(trial, global_pose.sequence if hasattr(global_pose, 'sequence') else global_pose)
    if output_dir is None:
        output_dir = Path.cwd() / f'{trial.name}_opensim'
    pipeline = OpenSimPipeline(cfg)
    artifacts = pipeline.run(trial_result, output_dir=output_dir, external_force_specs=forces.to_opensim_specs(), coordinate_set=cfg.coordinate_set)
    sto_path = artifacts.get('id_sto')
    generalized_forces_df = mot_to_dataframe(sto_path) if isinstance(sto_path, Path) else pd.DataFrame()
    external_loads_df = mot_to_dataframe(artifacts['force_table']) if isinstance(artifacts.get('force_table'), Path) else pd.DataFrame()
    summary_df = pd.DataFrame([
        {
            'model_path': cfg.model_path,
            'model_preset': artifacts.get('model_preset'),
            'id_executed': bool(artifacts.get('id_run', {}).get('ok')) if isinstance(artifacts.get('id_run'), dict) else False,
            'id_storage_exists': bool(isinstance(sto_path, Path) and sto_path.exists()),
            'n_generalized_force_rows': int(len(generalized_forces_df)),
            'n_external_load_rows': int(len(external_loads_df)),
        }
    ])
    result = IDResult(
        stage='id',
        df=generalized_forces_df,
        tables={'generalized_forces': generalized_forces_df, 'external_loads': external_loads_df, 'summary': summary_df},
        meta={'model_path': cfg.model_path, 'model_preset': artifacts.get('model_preset')},
        artifacts={k: v for k, v in artifacts.items() if isinstance(v, Path)},
        storage_path=sto_path if isinstance(sto_path, Path) else None,
    )
    return trial.register_stage('id', result)
