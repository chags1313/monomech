"""OpenSim scale / IK / ID pipeline helpers aligned to the original GATMA notebook."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..config import OpenSimConfig
from ..io.opensim import (
    mot_to_dataframe,
    sto_to_csv,
    storage_time_range,
    trc_to_dataframe,
    write_model_marker_trc,
    write_trc_from_trial,
)
from ..types import ExternalForceSpec, TrialResult
from ..utils.files import ensure_dir
from .external_loads import build_external_loads_bundle
from .presets import infer_model_preset
from .runtime import import_opensim, run_opensim_tool

MAX_MARKER_PAIRS_PER_BODY = 12


def _make_osim_array_double(osim, values):
    arr = osim.ArrayDouble()
    for i, v in enumerate(values):
        try:
            arr.append(float(v))
        except Exception:
            arr.insert(i, float(v))
    return arr


def _make_osim_array_str(osim, values):
    arr = osim.ArrayStr()
    for i, v in enumerate(values):
        try:
            arr.append(str(v))
        except Exception:
            arr.insert(i, str(v))
    return arr


def _load_model(osim, model_path: Path):
    model = osim.Model(str(model_path))
    model.finalizeConnections()
    model.initSystem()
    return model


def _clean_marker_name(token: str) -> str:
    token = (token or '').strip()
    if ':' in token:
        token = token.split(':')[-1]
    return token


def _model_marker_info(model) -> pd.DataFrame:
    rows = []
    marker_set = model.getMarkerSet()
    for i in range(marker_set.getSize()):
        marker = marker_set.get(i)
        marker_name = marker.getName()
        parent_frame_path = None
        base_frame_name = None
        try:
            parent_frame_path = marker.getParentFrameName()
        except Exception:
            parent_frame_path = ''
        try:
            base_frame_name = marker.getParentFrame().findBaseFrame().getName()
        except Exception:
            if parent_frame_path:
                base_frame_name = str(parent_frame_path).split('/')[-1]
        rows.append({'marker_name': marker_name, 'parent_frame_path': parent_frame_path, 'base_frame_name': base_frame_name})
    return pd.DataFrame(rows)


def _trc_marker_names(trc_path: Path) -> list[str]:
    df = trc_to_dataframe(trc_path)
    return [col[:-2] for col in df.columns if col.endswith('_x')]


def _common_model_and_trc_markers(model, trc_path: Path) -> list[str]:
    model_markers = set(_model_marker_info(model)['marker_name'].dropna().tolist())
    trc_markers = set(_trc_marker_names(trc_path))
    return sorted(model_markers.intersection(trc_markers))


def _body_to_common_markers(model, trc_path: Path) -> dict[str, list[str]]:
    info = _model_marker_info(model)
    common = set(_common_model_and_trc_markers(model, trc_path))
    info = info[info['marker_name'].isin(common)].copy()
    info = info.dropna(subset=['base_frame_name'])
    grouped: dict[str, list[str]] = {}
    for body_name, g in info.groupby('base_frame_name'):
        body_name = str(body_name)
        if body_name.lower() == 'ground':
            continue
        grouped[body_name] = sorted(g['marker_name'].tolist())
    return grouped


def _marker_pairs_for_body(markers: list[str], max_pairs: int = MAX_MARKER_PAIRS_PER_BODY) -> list[tuple[str, str]]:
    pairs = list(itertools.combinations(sorted(markers), 2))
    if len(pairs) > max_pairs:
        idxs = np.linspace(0, len(pairs) - 1, max_pairs, dtype=int)
        pairs = [pairs[i] for i in idxs]
    return pairs


def _auto_build_measurements_for_scale(osim, scale_tool, model, formatted_trc_path: Path) -> pd.DataFrame:
    grouped = _body_to_common_markers(model, formatted_trc_path)
    model_scaler = scale_tool.getModelScaler()
    kept = []
    for body_name, markers in grouped.items():
        if len(markers) < 2:
            continue
        pairs = _marker_pairs_for_body(markers)
        if not pairs:
            continue
        meas = osim.Measurement()
        meas.setName(body_name)
        meas.setApply(True)
        pair_set = meas.getMarkerPairSet()
        for m1, m2 in pairs:
            mp = osim.MarkerPair()
            mp.setMarkerName(0, m1)
            mp.setMarkerName(1, m2)
            pair_set.adoptAndAppend(mp)
        body_scale = osim.BodyScale()
        body_scale.setName(body_name)
        body_scale.setAxisNames(_make_osim_array_str(osim, ['X', 'Y', 'Z']))
        meas.getBodyScaleSet().adoptAndAppend(body_scale)
        model_scaler.addMeasurement(meas)
        kept.append({'body': body_name, 'n_markers': len(markers), 'n_pairs': len(pairs), 'markers': ', '.join(markers)})
    if not kept:
        raise RuntimeError('No auto-generated measurements were created for ScaleTool.')
    return pd.DataFrame(kept)


def _auto_build_marker_tasks(osim, task_set, marker_names: list[str], weight: float = 1.0):
    for name in marker_names:
        task = osim.IKMarkerTask()
        task.setName(str(name))
        task.setApply(True)
        task.setWeight(float(weight))
        task_set.adoptAndAppend(task)


def _auto_build_coordinate_tasks_from_unlocked_coords(osim, task_set, model, weight: float = 0.01):
    coord_set = model.getCoordinateSet()
    for i in range(coord_set.getSize()):
        coord = coord_set.get(i)
        try:
            locked = coord.getDefaultLocked()
        except Exception:
            locked = False
        if locked:
            continue
        task = osim.IKCoordinateTask()
        task.setName(coord.getName())
        task.setApply(False)
        task.setWeight(float(weight))
        task_set.adoptAndAppend(task)


def _find_best_scale_window(trc_path: Path, window_seconds: float, min_frames: int) -> tuple[float, float]:
    df = trc_to_dataframe(trc_path)
    if df.empty or 'time' not in df.columns:
        raise ValueError(f'No valid Time column found in {trc_path}')
    time = pd.to_numeric(df['time'], errors='coerce').to_numpy(dtype=float)
    valid = np.isfinite(time)
    df = df.loc[valid].reset_index(drop=True)
    time = time[valid]
    if len(time) < 2:
        return float(time[0]), float(time[-1])
    marker_names = _trc_marker_names(trc_path)
    if not marker_names:
        return float(time[0]), float(min(time[0] + window_seconds, time[-1]))
    def motion_score(start_idx: int, end_idx: int) -> tuple[float, float]:
        spans = []
        valid_counts = []
        for name in marker_names:
            cols = [f'{name}_x', f'{name}_y', f'{name}_z']
            xyz = df.iloc[start_idx:end_idx + 1][cols].to_numpy(dtype=float)
            mask = ~np.isnan(xyz).any(axis=1)
            xyz = xyz[mask]
            if len(xyz) < 2:
                continue
            spans.append(float(np.linalg.norm(np.nanmax(xyz, axis=0) - np.nanmin(xyz, axis=0))))
            valid_counts.append(float(mask.mean()))
        if not spans:
            return float('inf'), 0.0
        return float(np.median(spans)), float(np.mean(valid_counts))
    best = None
    for start_idx in range(len(time)):
        target_end_time = time[start_idx] + float(window_seconds)
        end_idx = int(np.searchsorted(time, target_end_time, side='right') - 1)
        if end_idx <= start_idx or (end_idx - start_idx + 1) < int(min_frames):
            continue
        motion, availability = motion_score(start_idx, end_idx)
        candidate = (motion, -availability, start_idx, end_idx)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        return float(time[0]), float(min(time[0] + window_seconds, time[-1]))
    _, _, s, e = best
    return float(time[s]), float(time[e])


@dataclass(slots=True)
class OpenSimPipeline:
    config: OpenSimConfig

    def _require_model_path(self) -> Path:
        if not self.config.model_path:
            raise ValueError('OpenSimConfig.model_path is required for OpenSim workflows.')
        return Path(self.config.model_path)

    def _select_scale_window(self, trc_path: Path) -> tuple[float, float]:
        if self.config.scale_time_window is not None:
            return float(self.config.scale_time_window[0]), float(self.config.scale_time_window[1])
        if self.config.scale_window_mode == 'full_trial':
            return storage_time_range(trc_path)
        return _find_best_scale_window(trc_path, window_seconds=self.config.scale_window_seconds, min_frames=self.config.scale_min_frames)

    def build_scale_tool(self, model_path: Path, formatted_trc_path: Path, outputs: dict[str, Path]):
        osim = import_opensim()
        model = _load_model(osim, model_path)
        scale_tool = osim.ScaleTool()
        scale_tool.setName(formatted_trc_path.stem.replace('_formatted', ''))
        scale_tool.setSubjectMass(0.0)
        scale_tool.setSubjectHeight(0.0)
        try:
            scale_tool.setPrintResultFiles(True)
        except Exception:
            pass
        generic_model_maker = scale_tool.getGenericModelMaker()
        generic_model_maker.setModelFileName(str(model_path))
        scale_window = self._select_scale_window(formatted_trc_path)
        scale_window_os = _make_osim_array_double(osim, scale_window)
        model_scaler = scale_tool.getModelScaler()
        model_scaler.setApply(True)
        model_scaler.setMarkerFileName(str(formatted_trc_path))
        model_scaler.setTimeRange(scale_window_os)
        model_scaler.setPreserveMassDist(False)
        model_scaler.setScalingOrder(_make_osim_array_str(osim, ['measurements']))
        model_scaler.setOutputModelFileName(str(outputs['scaled_only_model']))
        model_scaler.setOutputScaleFileName(str(outputs['applied_scale_xml']))
        measurement_df = _auto_build_measurements_for_scale(osim, scale_tool, model, formatted_trc_path)
        marker_placer = scale_tool.getMarkerPlacer()
        marker_placer.setApply(True)
        marker_placer.setMarkerFileName(str(formatted_trc_path))
        try:
            marker_placer.setStaticPoseFileName(str(formatted_trc_path))
        except Exception:
            pass
        marker_placer.setTimeRange(scale_window_os)
        marker_placer.setOutputModelFileName(str(outputs['scaled_model']))
        marker_placer.setOutputMotionFileName(str(outputs['scale_static_mot']))
        try:
            marker_placer.setMoveModelMarkers(True)
        except Exception:
            pass
        common_markers = _common_model_and_trc_markers(model, formatted_trc_path)
        _auto_build_marker_tasks(osim, marker_placer.getIKTaskSet(), common_markers, weight=self.config.scale_marker_weight)
        _auto_build_coordinate_tasks_from_unlocked_coords(osim, marker_placer.getIKTaskSet(), model, weight=0.01)
        setup_xml = outputs['setup_scale_xml']
        scale_tool.printToXML(str(setup_xml))
        return setup_xml, scale_window, measurement_df, len(common_markers)

    def build_ik_tool(self, scaled_model_path: Path, trc_path: Path, output_motion_path: Path):
        osim = import_opensim()
        model = _load_model(osim, scaled_model_path)
        tool = osim.InverseKinematicsTool()
        tool.setName(output_motion_path.stem)
        try:
            tool.setModel(model)
        except Exception:
            pass
        try:
            tool.setModelFileName(str(scaled_model_path))
        except Exception:
            pass
        tool.setMarkerDataFileName(str(trc_path))
        t0, t1 = storage_time_range(trc_path)
        tool.setStartTime(float(t0))
        tool.setEndTime(float(t1))
        tool.setOutputMotionFileName(str(output_motion_path))
        common_markers = _common_model_and_trc_markers(model, trc_path)
        _auto_build_marker_tasks(osim, tool.getIKTaskSet(), common_markers, weight=self.config.ik_marker_weight)
        _auto_build_coordinate_tasks_from_unlocked_coords(osim, tool.getIKTaskSet(), model, weight=0.01)
        setup_xml = output_motion_path.with_name(output_motion_path.stem + '_Setup_IK.xml')
        tool.printToXML(str(setup_xml))
        return setup_xml, (t0, t1), len(common_markers)

    def build_id_tool(self, scaled_model_path: Path, ik_mot_path: Path, external_loads_xml: Path, output_sto_path: Path):
        osim = import_opensim()
        tool = osim.InverseDynamicsTool()
        tool.setName(output_sto_path.stem)
        tool.setModelFileName(str(scaled_model_path))
        t0, t1 = storage_time_range(ik_mot_path)
        tool.setStartTime(float(t0))
        tool.setEndTime(float(t1))
        tool.setCoordinatesFileName(str(ik_mot_path))
        tool.setExternalLoadsFileName(str(external_loads_xml))
        tool.setResultsDir(str(output_sto_path.parent))
        tool.setOutputGenForceFileName(output_sto_path.name)
        tool.setLowpassCutoffFrequency(float(self.config.id_lowpass_cutoff))
        setup_xml = output_sto_path.with_name(output_sto_path.stem + '_Setup_ID.xml')
        tool.printToXML(str(setup_xml))
        return setup_xml, (t0, t1)

    def run(
        self,
        trial: TrialResult,
        output_dir: str | Path,
        external_force_specs: list[ExternalForceSpec] | None = None,
        coordinate_set: str = 'global',
    ) -> dict[str, Any]:
        model_path = self._require_model_path()
        out = ensure_dir(output_dir)
        artifacts: dict[str, Any] = {}
        preset = infer_model_preset(model_path, self.config.model_preset)
        artifacts['model_preset'] = preset.name if preset is not None else None

        if self.config.export_landmark_trc:
            landmark_trc = write_trc_from_trial(trial, out / f'{trial.name}_{coordinate_set}.trc', coordinate_set=coordinate_set)
            artifacts['landmark_trc'] = landmark_trc
            if self.config.write_csv_copies:
                landmark_csv = out / f'{trial.name}_{coordinate_set}.csv'
                trc_to_dataframe(landmark_trc).to_csv(landmark_csv, index=False)
                artifacts['landmark_trc_csv'] = landmark_csv

        marker_trc = None
        if self.config.export_marker_trc:
            marker_trc = write_model_marker_trc(trial, out / f'{trial.name}_{coordinate_set}_markers.trc', model_path=model_path, coordinate_set=coordinate_set)
            artifacts['marker_trc'] = marker_trc
            if self.config.write_csv_copies:
                marker_csv = out / f'{trial.name}_{coordinate_set}_markers.csv'
                trc_to_dataframe(marker_trc).to_csv(marker_csv, index=False)
                artifacts['marker_trc_csv'] = marker_csv
        working_trc = marker_trc or artifacts.get('landmark_trc')
        if working_trc is None:
            raise ValueError('No TRC export was produced for OpenSim.')

        outputs = {
            'scaled_only_model': out / f'{trial.name}_scaledOnly.osim',
            'scaled_model': out / f'{trial.name}_scaled.osim',
            'applied_scale_xml': out / f'{trial.name}_ScaleSet_applied.xml',
            'scale_static_mot': out / f'{trial.name}_scale_static.mot',
            'setup_scale_xml': out / f'{trial.name}_Setup_Scale.xml',
            'ik_mot': out / f'{trial.name}_ik.mot',
            'setup_ik_xml': out / f'{trial.name}_Setup_IK.xml',
            'id_sto': out / f'{trial.name}_id.sto',
            'id_setup_xml': out / f'{trial.name}_Setup_ID.xml',
        }

        scaled_model_path = model_path
        if self.config.run_scale:
            scale_setup, scale_window, measurement_df, n_scale_markers = self.build_scale_tool(model_path, working_trc, outputs)
            artifacts['scale_setup_xml'] = scale_setup
            artifacts['scale_measurements_csv'] = out / f'{trial.name}_scale_measurements.csv'
            measurement_df.to_csv(artifacts['scale_measurements_csv'], index=False)
            artifacts['scale_window'] = scale_window
            artifacts['n_scale_markers'] = n_scale_markers
            artifacts['scale_run'] = run_opensim_tool(scale_setup, 'ScaleTool', use_subprocess=self.config.use_subprocess)
            scaled_model_path = outputs['scaled_model'] if outputs['scaled_model'].exists() else model_path
            if outputs['scale_static_mot'].exists() and self.config.write_csv_copies:
                artifacts['scale_static_csv'] = sto_to_csv(outputs['scale_static_mot'])
            if outputs['scaled_model'].exists():
                artifacts['scaled_model'] = outputs['scaled_model']

        if self.config.run_ik:
            ik_setup, ik_window, n_ik_markers = self.build_ik_tool(scaled_model_path, working_trc, outputs['ik_mot'])
            artifacts['ik_setup_xml'] = ik_setup
            artifacts['ik_window'] = ik_window
            artifacts['n_ik_markers'] = n_ik_markers
            artifacts['ik_run'] = run_opensim_tool(ik_setup, 'InverseKinematicsTool', use_subprocess=self.config.use_subprocess)
            artifacts['ik_mot'] = outputs['ik_mot']
            if outputs['ik_mot'].exists() and self.config.write_csv_copies:
                artifacts['ik_csv'] = sto_to_csv(outputs['ik_mot'])

        if self.config.run_id:
            if not external_force_specs:
                raise ValueError('external_force_specs are required when run_id=True')
            if 'ik_mot' not in artifacts:
                raise ValueError('Inverse dynamics requires an IK motion file. Enable run_ik=True.')
            bundle = build_external_loads_bundle(trial, external_force_specs, out, stem=trial.name)
            artifacts.update(bundle)
            id_setup, id_window = self.build_id_tool(scaled_model_path, artifacts['ik_mot'], bundle['external_loads_xml'], outputs['id_sto'])
            artifacts['id_setup_xml'] = id_setup
            artifacts['id_window'] = id_window
            artifacts['id_run'] = run_opensim_tool(id_setup, 'InverseDynamicsTool', use_subprocess=self.config.use_subprocess)
            artifacts['id_sto'] = outputs['id_sto']
            if outputs['id_sto'].exists() and self.config.write_csv_copies:
                artifacts['id_csv'] = sto_to_csv(outputs['id_sto'])

        return artifacts
