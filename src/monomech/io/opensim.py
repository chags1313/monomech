"""OpenSim-oriented writers."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

from ..constants import LANDMARK_NAMES
from ..opensim.presets import infer_model_preset, resolve_marker_point
from ..types import ExternalForceSpec, TrialResult
from ..utils.files import ensure_dir


def _map_xyz_array_to_opensim(xyz: np.ndarray) -> np.ndarray:
    mapped = np.empty_like(xyz, dtype=float)
    mapped[..., 0] = xyz[..., 2]
    mapped[..., 1] = -xyz[..., 1]
    mapped[..., 2] = xyz[..., 0]
    return mapped


def _pose_to_mapped_xyz(
    trial: TrialResult,
    coordinate_set: str = "global",
    ground_y: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    pose = trial.get_pose(coordinate_set)
    mapped = _map_xyz_array_to_opensim(pose.xyz)
    if ground_y:
        ymin = np.nanmin(mapped[..., 1])
        if np.isfinite(ymin):
            mapped[..., 1] = mapped[..., 1] - ymin
    return pose.time_s, mapped


def write_trc_from_trial(
    trial: TrialResult,
    output_path: str | Path,
    coordinate_set: str = "global",
    units: str = "m",
    ground_y: bool = True,
    marker_names: list[str] | None = None,
    xyz: np.ndarray | None = None,
    time_s: np.ndarray | None = None,
) -> Path:
    path = Path(output_path)
    ensure_dir(path.parent)

    if xyz is None or time_s is None:
        time_s, xyz = _pose_to_mapped_xyz(
            trial,
            coordinate_set=coordinate_set,
            ground_y=ground_y,
        )
    assert xyz is not None and time_s is not None
    units_header = "mm" if str(units).lower() == "mm" else "m"
    scale = 1000.0 if units_header == "mm" else 1.0
    n_frames, n_markers, _ = xyz.shape
    marker_names = marker_names or LANDMARK_NAMES[:n_markers]

    lines: list[str] = []
    lines.append(f"PathFileType\t4\t(X/Y/Z)\t{path.name}")
    lines.append(
        "DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\tOrigDataRate\tOrigDataStartFrame\tOrigNumFrames"
    )
    lines.append(
        f"{trial.fps:.6f}\t{trial.fps:.6f}\t{n_frames}\t{n_markers}\t{units_header}\t{trial.fps:.6f}\t1\t{n_frames}"
    )
    name_cells = ["Frame#", "Time"]
    for name in marker_names[:n_markers]:
        name_cells.extend([name, "", ""])
    lines.append("\t".join(name_cells))
    axis_cells = ["", ""]
    for idx in range(1, n_markers + 1):
        axis_cells.extend([f"X{idx}", f"Y{idx}", f"Z{idx}"])
    lines.append("\t".join(axis_cells))

    for frame_idx in range(n_frames):
        row = [str(frame_idx + 1), f"{float(time_s[frame_idx]):.6f}"]
        for marker_idx in range(n_markers):
            point = xyz[frame_idx, marker_idx, :] * scale
            row.extend(
                [
                    f"{float(point[0]):.6f}",
                    f"{float(point[1]):.6f}",
                    f"{float(point[2]):.6f}",
                ]
            )
        lines.append("\t".join(row))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _model_marker_xyz(
    trial: TrialResult,
    model_path: str | Path | None,
    coordinate_set: str = "global",
) -> tuple[list[str], np.ndarray, np.ndarray]:
    preset = infer_model_preset(model_path)
    if preset is None:
        raise ValueError("No model preset available for model-specific marker export.")
    pose = trial.get_pose(coordinate_set)
    marker_names = preset.marker_names()
    raw = np.full((pose.n_frames, len(marker_names), 3), np.nan, dtype=float)
    for j, name in enumerate(marker_names):
        resolver = preset.marker_map[name]
        for i in range(pose.n_frames):
            raw[i, j, :] = resolve_marker_point(pose, i, resolver)
    mapped = _map_xyz_array_to_opensim(raw)
    ymin = np.nanmin(mapped[..., 1])
    if np.isfinite(ymin):
        mapped[..., 1] = mapped[..., 1] - ymin
    return marker_names, pose.time_s.copy(), mapped


def write_model_marker_trc(
    trial: TrialResult,
    output_path: str | Path,
    *,
    model_path: str | Path | None,
    coordinate_set: str = "global",
    units: str = "m",
) -> Path:
    marker_names, time_s, mapped = _model_marker_xyz(
        trial,
        model_path=model_path,
        coordinate_set=coordinate_set,
    )
    return write_trc_from_trial(
        trial,
        output_path,
        coordinate_set=coordinate_set,
        units=units,
        ground_y=False,
        marker_names=marker_names,
        xyz=mapped,
        time_s=time_s,
    )


def trc_to_dataframe(trc_path: str | Path) -> pd.DataFrame:
    path = Path(trc_path)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if len(lines) < 5:
        return pd.DataFrame()
    marker_row = lines[3].split("\t")
    columns = ["frame", "time"]
    marker_names: list[str] = []
    for idx in range(2, len(marker_row), 3):
        name = marker_row[idx].strip()
        if name:
            marker_names.append(name)
            columns.extend([f"{name}_x", f"{name}_y", f"{name}_z"])
    data = []
    for line in lines[5:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < len(columns):
            parts += [""] * (len(columns) - len(parts))
        data.append(parts[: len(columns)])
    if not data:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(data, columns=columns)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def trc_to_long_dataframe(trc_path: str | Path) -> pd.DataFrame:
    wide = trc_to_dataframe(trc_path)
    if wide.empty:
        return pd.DataFrame(columns=["frame", "time", "marker", "x", "y", "z"])
    markers = sorted({col[:-2] for col in wide.columns if col.endswith("_x")})
    rows = []
    for _, row in wide.iterrows():
        for marker in markers:
            rows.append(
                {
                    "frame": int(row["frame"]),
                    "time": float(row["time"]),
                    "marker": marker,
                    "x": float(row.get(f"{marker}_x", np.nan)),
                    "y": float(row.get(f"{marker}_y", np.nan)),
                    "z": float(row.get(f"{marker}_z", np.nan)),
                }
            )
    return pd.DataFrame(rows)


def mot_to_dataframe(mot_path: str | Path) -> pd.DataFrame:
    path = Path(mot_path)
    if not path.exists():
        return pd.DataFrame()
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    start_idx = None
    for idx, line in enumerate(lines):
        s = line.strip().lower()
        if s == "endheader":
            start_idx = idx + 1
            break
        if line.strip() and line.strip().split()[0].lower() == "time":
            start_idx = idx
            break
    if start_idx is None or start_idx >= len(lines):
        return pd.DataFrame()
    return pd.read_csv(
        io.StringIO("\n".join(lines[start_idx:])),
        sep=r"\s+|\t+",
        engine="python",
    )


def storage_time_range(path: str | Path) -> tuple[float, float]:
    df = mot_to_dataframe(path)
    if "time" not in df.columns or df.empty:
        raise ValueError(f"No valid time column found in {path}")
    t = pd.to_numeric(df["time"], errors="coerce").dropna().to_numpy(dtype=float)
    return float(t[0]), float(t[-1])


def write_sto_table(
    df: pd.DataFrame,
    output_path: str | Path,
    name: str = "storage",
    in_degrees: bool = False,
) -> Path:
    path = Path(output_path)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"{name}\n")
        f.write("version=1\n")
        f.write(f"nRows={len(df)}\n")
        f.write(f"nColumns={len(df.columns)}\n")
        f.write(f"inDegrees={'yes' if in_degrees else 'no'}\n")
        f.write("endheader\n")
        df.to_csv(f, sep="\t", index=False, float_format="%.8f")
    return path


def sto_to_csv(path: str | Path, output_csv: str | Path | None = None) -> Path:
    src = Path(path)
    dst = Path(output_csv) if output_csv is not None else src.with_suffix(".csv")
    df = mot_to_dataframe(src)
    df.to_csv(dst, index=False)
    return dst


def _resolve_vector(
    spec_value,
    trial: TrialResult,
    frame_idx: int,
    time_s: float,
) -> tuple[float, float, float]:
    if callable(spec_value):
        value = spec_value(trial, frame_idx, time_s)
    else:
        value = spec_value
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 2:
        arr = arr[frame_idx]
    if arr.shape != (3,):
        raise ValueError(f"Vector provider must yield shape (3,), got {arr.shape}")
    return float(arr[0]), float(arr[1]), float(arr[2])


def external_force_table(trial: TrialResult, specs: list[ExternalForceSpec]) -> pd.DataFrame:
    if not specs:
        raise ValueError("At least one ExternalForceSpec is required.")
    time_s = (
        trial.get_pose("global").time_s
        if trial.global_pose is not None
        else trial.get_pose("pnp").time_s
    )
    rows = []
    for frame_idx, t in enumerate(time_s):
        row = {"time": float(t)}
        for spec in specs:
            prefix = spec.name
            fx, fy, fz = _resolve_vector(spec.force, trial, frame_idx, float(t))
            px, py, pz = _resolve_vector(spec.point, trial, frame_idx, float(t))
            if spec.torque is None:
                tx, ty, tz = 0.0, 0.0, 0.0
            else:
                tx, ty, tz = _resolve_vector(spec.torque, trial, frame_idx, float(t))
            row[f"{prefix}_fx"] = fx
            row[f"{prefix}_fy"] = fy
            row[f"{prefix}_fz"] = fz
            row[f"{prefix}_px"] = px
            row[f"{prefix}_py"] = py
            row[f"{prefix}_pz"] = pz
            row[f"{prefix}_tx"] = tx
            row[f"{prefix}_ty"] = ty
            row[f"{prefix}_tz"] = tz
        rows.append(row)
    return pd.DataFrame(rows)


def write_external_loads_xml(
    specs: list[ExternalForceSpec],
    output_path: str | Path,
    data_file: str | Path,
) -> Path:
    path = Path(output_path)
    ensure_dir(path.parent)

    root = ET.Element("OpenSimDocument", Version="40000")
    ext_loads = ET.SubElement(root, "ExternalLoads", name=path.stem)
    objects = ET.SubElement(ext_loads, "objects")
    ET.SubElement(ext_loads, "groups")
    ET.SubElement(ext_loads, "datafile").text = str(data_file)

    for spec in specs:
        exf = ET.SubElement(objects, "ExternalForce", name=spec.name)
        ET.SubElement(exf, "applied_to_body").text = spec.applied_to_body
        ET.SubElement(exf, "force_expressed_in_body").text = spec.force_expressed_in_body
        ET.SubElement(exf, "point_expressed_in_body").text = spec.point_expressed_in_body
        force_id = spec.force_identifier or f"{spec.name}_f"
        point_id = spec.point_identifier or f"{spec.name}_p"
        torque_id = spec.torque_identifier or f"{spec.name}_t"
        ET.SubElement(exf, "force_identifier").text = force_id
        ET.SubElement(exf, "point_identifier").text = point_id
        ET.SubElement(exf, "torque_identifier").text = torque_id
        ET.SubElement(exf, "data_source_name").text = str(data_file)

    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path
