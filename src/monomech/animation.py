# ruff: noqa: E501

from __future__ import annotations

import io
import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(slots=True)
class OpenSimAnimationResult:
    """Paths and summary data from an OpenSim GLB animation export."""

    glb_path: Path
    marker_dataframe: pd.DataFrame | None
    metadata: dict[str, Any]

    def to_dataframe(self) -> pd.DataFrame:
        if self.marker_dataframe is None:
            return pd.DataFrame()
        return self.marker_dataframe.copy()


@dataclass(slots=True)
class OpenSimVisualizerResult:
    """Notebook-friendly HTML visualizer output."""

    html_path: Path
    metadata: dict[str, Any]

    def _repr_html_(self) -> str:
        uri = self.html_path.resolve().as_uri()
        return (
            f'<iframe src="{uri}" width="100%" height="860" '
            'style="border:0;border-radius:8px;overflow:hidden;"></iframe>'
        )


def _require_animation_dependencies():
    missing = []
    try:
        from .opensim_runtime import require_opensim

        osim = require_opensim()
    except Exception:
        osim = None
        missing.append("pyopensim")
    try:
        import pyvista as pv  # type: ignore
    except Exception:
        pv = None
        missing.append("pyvista")
    try:
        import pygltflib  # type: ignore
    except Exception:
        pygltflib = None
        missing.append("pygltflib")

    if missing:
        packages = ", ".join(missing)
        raise ImportError(
            "OpenSim animation export requires optional packages that are not installed: "
            f"{packages}. Install them with `python -m pip install \"monomech[animation]\"`."
        )
    return osim, pv, pygltflib


def _require_opensim_dependency():
    try:
        from .opensim_runtime import require_opensim

        osim = require_opensim()
    except Exception as exc:
        raise ImportError(
            "OpenSim marker extraction requires OpenSim bindings. Install "
            '`python -m pip install "monomech[opensim]"` or '
            '`python -m pip install "monomech[animation]"`.'
        ) from exc
    return osim


def _tag(elem: ET.Element) -> str:
    return elem.tag.split("}")[-1].lower()


def _float_triplet(value: str | None) -> tuple[float, float, float] | None:
    if not value:
        return None
    try:
        values = tuple(float(v) for v in str(value).replace(",", " ").split())
    except Exception:
        return None
    if len(values) != 3:
        return None
    return values


def _hex_to_rgb01(hex_color: str) -> tuple[float, float, float]:
    color = hex_color.strip().lstrip("#")
    if len(color) != 6:
        raise ValueError(f"Expected a 6-digit hex color such as '#2b2f36', got {hex_color!r}.")
    return (
        int(color[0:2], 16) / 255.0,
        int(color[2:4], 16) / 255.0,
        int(color[4:6], 16) / 255.0,
    )


def _simtk_vec3_to_np(vec) -> np.ndarray:
    return np.array([vec.get(0), vec.get(1), vec.get(2)], dtype=float)


def _simtk_rot_to_np(rot) -> np.ndarray:
    return np.array(
        [
            [rot.get(0, 0), rot.get(0, 1), rot.get(0, 2)],
            [rot.get(1, 0), rot.get(1, 1), rot.get(1, 2)],
            [rot.get(2, 0), rot.get(2, 1), rot.get(2, 2)],
        ],
        dtype=float,
    )


def _euler_deg_xyz_to_matrix(rx_deg: float, ry_deg: float, rz_deg: float) -> np.ndarray:
    rx, ry, rz = np.deg2rad([rx_deg, ry_deg, rz_deg])
    rx_mat = np.array(
        [[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]]
    )
    ry_mat = np.array(
        [[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]]
    )
    rz_mat = np.array(
        [[np.cos(rz), -np.sin(rz), 0], [np.sin(rz), np.cos(rz), 0], [0, 0, 1]]
    )
    return rz_mat @ ry_mat @ rx_mat


def _matrix_to_quat_xyzw(matrix: np.ndarray) -> np.ndarray:
    trace = float(np.trace(matrix))
    if trace > 0:
        scale = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * scale
        x = (matrix[2, 1] - matrix[1, 2]) / scale
        y = (matrix[0, 2] - matrix[2, 0]) / scale
        z = (matrix[1, 0] - matrix[0, 1]) / scale
    elif matrix[0, 0] > matrix[1, 1] and matrix[0, 0] > matrix[2, 2]:
        scale = math.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
        w = (matrix[2, 1] - matrix[1, 2]) / scale
        x = 0.25 * scale
        y = (matrix[0, 1] + matrix[1, 0]) / scale
        z = (matrix[0, 2] + matrix[2, 0]) / scale
    elif matrix[1, 1] > matrix[2, 2]:
        scale = math.sqrt(1.0 - matrix[0, 0] + matrix[1, 1] - matrix[2, 2]) * 2.0
        w = (matrix[0, 2] - matrix[2, 0]) / scale
        x = (matrix[0, 1] + matrix[1, 0]) / scale
        y = 0.25 * scale
        z = (matrix[1, 2] + matrix[2, 1]) / scale
    else:
        scale = math.sqrt(1.0 - matrix[0, 0] - matrix[1, 1] + matrix[2, 2]) * 2.0
        w = (matrix[1, 0] - matrix[0, 1]) / scale
        x = (matrix[0, 2] + matrix[2, 0]) / scale
        y = (matrix[1, 2] + matrix[2, 1]) / scale
        z = 0.25 * scale
    quat = np.array([x, y, z, w], dtype=np.float32)
    return quat / max(1e-12, float(np.linalg.norm(quat)))


def _read_header_lines(path: Path, max_lines: int = 300) -> tuple[list[str], list[str]]:
    lines = path.read_text(errors="ignore").splitlines(keepends=True)
    return lines[:max_lines], lines


def _in_degrees_from_header(header_lines: list[str]) -> bool:
    for line in header_lines:
        if "endheader" in line.lower():
            break
        match = re.search(r"inDegrees\s*=\s*([A-Za-z0-9]+)", line)
        if match:
            return match.group(1).strip().lower() in {"yes", "true", "1"}
    return False


def _read_mot_or_sto(path: Path, osim) -> tuple[bool, np.ndarray, list[str], np.ndarray]:
    header, all_lines = _read_header_lines(path)
    in_degrees = _in_degrees_from_header(header)

    try:
        table = osim.TimeSeriesTable(str(path))
        nrows = table.getNumRows()
        ncols = table.getNumColumns()
        times = np.array(list(table.getIndependentColumn()), dtype=float)
        labels = [table.getColumnLabel(j) for j in range(ncols)]
        data = np.empty((nrows, ncols), dtype=float)
        for j, label in enumerate(labels):
            col = table.getDependentColumn(label)
            data[:, j] = [float(col.get(i)) for i in range(nrows)]
        return in_degrees, times, labels, data
    except Exception:
        start = 0
        for i, line in enumerate(all_lines[:300]):
            if "endheader" in line.lower():
                start = i + 1
                break
        df = pd.read_csv(
            io.StringIO("".join(all_lines[start:])),
            sep=r"\s+",
            engine="python",
            comment="%",
        )
        if "time" in df.columns:
            times = df["time"].to_numpy(dtype=float)
            labels = [c for c in df.columns if c != "time"]
            data = df[labels].to_numpy(dtype=float)
        else:
            times = np.arange(len(df), dtype=float)
            labels = list(df.columns)
            data = df.to_numpy(dtype=float)
        return in_degrees, times, labels, data


def _parse_geometry(osim_path: Path) -> list[dict[str, Any]]:
    tree = ET.parse(osim_path)
    root = tree.getroot()
    specs: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None]] = set()

    for elem in root.iter():
        if _tag(elem) != "mesh":
            continue
        mesh_file = elem.attrib.get("mesh_file") or ""
        frame_path = elem.attrib.get("frame") or elem.attrib.get("frame_name") or ""
        scale = None
        loc = None
        rot = None

        for child in list(elem):
            child_tag = _tag(child)
            text = child.text.strip() if child.text else ""
            if not mesh_file and child_tag in {"mesh_file", "filename", "file", "mesh"}:
                mesh_file = text
            elif not frame_path and child_tag in {"frame", "frame_name"}:
                frame_path = text
            elif child_tag in {"scale_factors", "scale"}:
                scale = _float_triplet(text) or scale
            elif child_tag in {"translation", "location", "offset", "trans"}:
                loc = _float_triplet(text) or loc
            elif child_tag in {"rotation", "orientation", "rot"}:
                rot = _float_triplet(text) or rot

        if scale is None:
            sx = elem.attrib.get("scale_factors_x")
            sy = elem.attrib.get("scale_factors_y")
            sz = elem.attrib.get("scale_factors_z")
            if sx and sy and sz:
                scale = _float_triplet(f"{sx} {sy} {sz}")

        key = ("mesh", mesh_file, frame_path or None)
        if mesh_file and key not in seen:
            specs.append(
                {
                    "mesh_file": mesh_file,
                    "frame_path": frame_path or None,
                    "body_owner": None,
                    "scale": scale,
                    "local_translation": loc,
                    "local_rotation_deg": rot,
                }
            )
            seen.add(key)

    for body in root.iter():
        if _tag(body) != "body":
            continue
        body_name = body.attrib.get("name") or body.attrib.get("name_")
        if not body_name:
            continue
        for sub in body.iter():
            if _tag(sub) not in {"displaygeometry", "mesh"}:
                continue
            mesh_file = sub.attrib.get("geometry_file") or sub.attrib.get("mesh_file") or ""
            loc = None
            rot = None
            scale = None
            for child in list(sub):
                child_tag = _tag(child)
                text = child.text.strip() if child.text else ""
                geometry_tags = {"geometry_file", "mesh_file", "filename", "file", "mesh"}
                if not mesh_file and child_tag in geometry_tags:
                    mesh_file = text
                elif child_tag in {"translation", "location", "offset", "trans"}:
                    loc = _float_triplet(text) or loc
                elif child_tag in {"rotation", "orientation", "rot"}:
                    rot = _float_triplet(text) or rot
                elif child_tag in {"scale_factors", "scale"}:
                    scale = _float_triplet(text) or scale

            if scale is None:
                sx = sub.attrib.get("scale_factors_x")
                sy = sub.attrib.get("scale_factors_y")
                sz = sub.attrib.get("scale_factors_z")
                if sx and sy and sz:
                    scale = _float_triplet(f"{sx} {sy} {sz}")

            key = ("bodygeom", body_name, mesh_file)
            if mesh_file and key not in seen:
                specs.append(
                    {
                        "mesh_file": mesh_file,
                        "frame_path": None,
                        "body_owner": body_name,
                        "scale": scale,
                        "local_translation": loc,
                        "local_rotation_deg": rot,
                    }
                )
                seen.add(key)
    return specs


def _resolve_geometry_dirs(osim_path: Path, geom_dir: str | Path | None) -> list[Path]:
    candidates: list[Path] = []
    if geom_dir is not None:
        candidates.append(Path(geom_dir).expanduser().resolve())
    candidates.extend(
        [
            osim_path.parent / "Geometry",
            osim_path.parent / "geometry",
            osim_path.parent,
        ]
    )
    out = []
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir() and candidate not in out:
            out.append(candidate)
    return out


def _find_geometry_file(mesh_file: str, geometry_dirs: list[Path]) -> Path | None:
    if not mesh_file:
        return None
    mesh_path = Path(mesh_file)
    candidates = [mesh_path]
    if not mesh_path.is_absolute():
        candidates.extend([directory / mesh_file for directory in geometry_dirs])
        candidates.extend([directory / mesh_path.name for directory in geometry_dirs])
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except Exception:
            continue
        if resolved.is_file():
            return resolved
    return None


def _load_polydata(path: Path, pv, *, target_reduction, target_error, preserve_topology):
    mesh = pv.read(str(path))
    if not isinstance(mesh, pv.PolyData):
        mesh = mesh.extract_surface()
    mesh = mesh.triangulate()
    try:
        if target_reduction is not None:
            mesh = mesh.decimate_pro(
                target_reduction=float(target_reduction),
                preserve_topology=bool(preserve_topology),
            )
        elif target_error is not None:
            mesh = mesh.decimate(target_error=float(target_error))
    except Exception:
        pass
    return mesh


def _coordinate_mapping(
    model,
    labels: list[str],
    *,
    in_degrees: bool,
) -> tuple[list[tuple[Any, int, bool]], list[str]]:
    coordset = model.getCoordinateSet()
    coord_names = [coordset.get(i).getName() for i in range(coordset.getSize())]
    by_full = {name: coordset.get(i) for i, name in enumerate(coord_names)}
    suffix_map = {name.split("/")[-1]: name for name in coord_names}
    lower_suffix_map = {key.lower(): value for key, value in suffix_map.items()}
    lower_exact_map = {name.lower(): name for name in coord_names}

    def coord_for_label(label: str):
        if label in by_full:
            return by_full[label], label
        low = label.lower()
        if low in lower_exact_map:
            true_name = lower_exact_map[low]
            return by_full[true_name], true_name
        suffix = label.split("/")[-1]
        if suffix in suffix_map:
            true_name = suffix_map[suffix]
            return by_full[true_name], true_name
        if suffix.lower() in lower_suffix_map:
            true_name = lower_suffix_map[suffix.lower()]
            return by_full[true_name], true_name
        return None, None

    def is_rotational(coord, true_name: str) -> bool:
        try:
            motion_type = str(coord.getMotionType())
            if "Rot" in motion_type:
                return True
            if "Trans" in motion_type:
                return False
        except Exception:
            pass
        suffix = true_name.split("/")[-1]
        if suffix.endswith(("_tx", "_ty", "_tz")):
            return False
        return True

    mapping = []
    unmatched = []
    for j, label in enumerate(labels):
        coord, true_name = coord_for_label(label)
        if coord is None or true_name is None:
            unmatched.append(label)
            continue
        mapping.append((coord, j, bool(in_degrees and is_rotational(coord, true_name))))
    return mapping, unmatched


def _canonicalize_body_target(
    model,
    name_to_body: dict[str, Any],
    body_names: list[str],
    stem: str,
):
    stem_lower = stem.lower()
    side = None
    if "_r" in stem_lower or stem_lower.endswith("right"):
        side = "r"
    elif "_l" in stem_lower or stem_lower.endswith("left") or stem_lower.startswith("l_"):
        side = "l"
    suffix = f"_{side}" if side else ""

    if "foot" in stem_lower or "bofoot" in stem_lower:
        for candidate in (f"foot{suffix}", f"calcn{suffix}", f"toes{suffix}", f"talus{suffix}"):
            if candidate.lower() in name_to_body:
                return name_to_body[candidate.lower()]

    for root in ("patella", "fibula", "tibia", "femur", "talus"):
        if root in stem_lower:
            candidate = f"{root}{suffix}"
            if candidate.lower() in name_to_body:
                return name_to_body[candidate.lower()]

    for candidate in ("pelvis", "sacrum"):
        if candidate in stem_lower and candidate in name_to_body:
            return name_to_body[candidate]

    matches = [
        (body_name, len(body_name))
        for body_name in body_names
        if body_name.lower() in stem_lower
    ]
    if matches:
        matches.sort(key=lambda item: -item[1])
        return name_to_body[matches[0][0].lower()]
    return model.getGround()


def _thin_track(
    times: np.ndarray,
    translation: np.ndarray,
    rotation: np.ndarray,
    *,
    pos_tol: float | None,
    rot_tol_rad: float | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if pos_tol is None and rot_tol_rad is None:
        return times, translation, rotation
    keep = [0]
    for i in range(1, len(times) - 1):
        dp = float(np.linalg.norm(translation[i] - translation[keep[-1]]))
        dot = float(abs(np.dot(rotation[i], rotation[keep[-1]])))
        dq = 2.0 * math.acos(min(1.0, max(-1.0, dot)))
        if (pos_tol is not None and dp > pos_tol) or (rot_tol_rad is not None and dq > rot_tol_rad):
            keep.append(i)
    if keep[-1] != len(times) - 1:
        keep.append(len(times) - 1)
    keep_array = np.unique(np.asarray(keep, dtype=int))
    return times[keep_array], translation[keep_array], rotation[keep_array]


def _is_origin_node(
    translation: np.ndarray,
    rotation: np.ndarray,
    *,
    pos_tol: float,
    rot_tol_rad: float | None,
) -> bool:
    if float(np.linalg.norm(translation, axis=1).max()) > pos_tol:
        return False
    if rot_tol_rad is None:
        return True
    identity = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
    dots = np.abs(np.clip((rotation * identity).sum(axis=1), -1.0, 1.0))
    angle = 2.0 * np.arccos(dots)
    return float(angle.max()) <= rot_tol_rad


def _id_metadata(id_path: str | Path | None, osim) -> dict[str, Any] | None:
    if id_path is None:
        return None
    path = Path(id_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"ID STO/MOT file not found: {path}")
    _, times, labels, _ = _read_mot_or_sto(path, osim)
    return {
        "path": str(path),
        "rows": int(len(times)),
        "columns": labels,
        "time_range": [float(times[0]), float(times[-1])] if len(times) else None,
    }


def extract_opensim_marker_positions(
    *,
    osim_path: str | Path,
    mot_path: str | Path,
    t_start: float | None = None,
    t_end: float | None = None,
    stride: int = 1,
) -> pd.DataFrame:
    """Evaluate OpenSim model marker positions through an IK motion file."""

    osim = _require_opensim_dependency()
    osim_path = Path(osim_path).expanduser().resolve()
    mot_path = Path(mot_path).expanduser().resolve()
    if not osim_path.is_file():
        raise FileNotFoundError(f"OSIM file not found: {osim_path}")
    if not mot_path.is_file():
        raise FileNotFoundError(f"IK MOT/STO file not found: {mot_path}")

    model = osim.Model(str(osim_path))
    state = model.initSystem()
    in_degrees, all_times, labels, all_data = _read_mot_or_sto(mot_path, osim)
    mask = np.ones_like(all_times, dtype=bool)
    if t_start is not None:
        mask &= all_times >= float(t_start)
    if t_end is not None:
        mask &= all_times <= float(t_end)
    all_times = all_times[mask]
    all_data = all_data[mask]
    if len(all_times) == 0:
        raise ValueError("No frames remain after applying the selected time window.")

    stride = max(1, int(stride))
    frame_idx = np.arange(len(all_times))[::stride]
    times = all_times[frame_idx]
    data = all_data[frame_idx]
    mapping, unmatched = _coordinate_mapping(model, labels, in_degrees=in_degrees)
    if not mapping:
        raise ValueError(
            "None of the MOT/STO columns matched coordinates in the OpenSim model. "
            f"First unmatched labels: {unmatched[:8]}"
        )

    marker_set = model.getMarkerSet()
    marker_names = [marker_set.get(i).getName() for i in range(marker_set.getSize())]
    marker_positions = np.zeros((len(times), 3 * len(marker_names)), dtype=float)
    degree_to_rad = np.pi / 180.0

    for frame_number, row in enumerate(data):
        for coord, col, convert_degrees in mapping:
            value = float(row[col])
            if convert_degrees:
                value *= degree_to_rad
            try:
                coord.setValue(state, value, True)
            except Exception:
                coord.setValue(state, value)
        model.realizePosition(state)

        for marker_idx in range(marker_set.getSize()):
            marker = marker_set.get(marker_idx)
            marker_local = _simtk_vec3_to_np(marker.get_location())
            parent = marker.getParentFrame()
            parent_transform = parent.getTransformInGround(state)
            parent_r = _simtk_rot_to_np(parent_transform.R())
            marker_global = _simtk_vec3_to_np(parent_transform.p()) + parent_r @ marker_local
            marker_positions[frame_number, 3 * marker_idx : 3 * marker_idx + 3] = marker_global

    columns = []
    for name in marker_names:
        columns.extend([f"{name}_x", f"{name}_y", f"{name}_z"])
    df = pd.DataFrame(marker_positions, index=pd.Index(times, name="time"), columns=columns)
    df.attrs["unmatched_coordinates"] = unmatched
    return df


def save_opensim_animation(
    *,
    osim_path: str | Path,
    mot_path: str | Path,
    out_glb_path: str | Path,
    geom_dir: str | Path | None = None,
    id_path: str | Path | None = None,
    bone_hex: str = "#2b2f36",
    opacity: float = 1.0,
    skip_ground_fallbacks: bool = True,
    lift_pelvis_by: float = 0.0,
    t_start: float | None = None,
    t_end: float | None = None,
    stride: int = 1,
    thin_pos_tol: float | None = 1e-4,
    thin_rot_tol_deg: float | None = 0.05,
    drop_static_nodes: bool = True,
    decimate_target_reduction: float | None = None,
    decimate_error: float | None = None,
    decimate_preserve_topology: bool = False,
    enforce_quat_continuity: bool = True,
    drop_origin_nodes: bool = True,
    origin_pos_tol: float = 1e-5,
    origin_rot_tol_deg: float | None = None,
    return_markers: bool = True,
    quiet: bool = False,
) -> OpenSimAnimationResult:
    """Export an animated OpenSim model to a single binary glTF/GLB file.

    The animation is driven by IK coordinates from `mot_path`. If `id_path` is
    provided, inverse-dynamics metadata is embedded in the GLB extras so one
    file carries the visual motion and the kinetics provenance.
    """

    osim, pv, pygltflib = _require_animation_dependencies()
    from pygltflib import (  # type: ignore
        ARRAY_BUFFER,
        ELEMENT_ARRAY_BUFFER,
        FLOAT,
        GLTF2,
        SCALAR,
        UNSIGNED_INT,
        VEC3,
        VEC4,
        Accessor,
        Animation,
        AnimationChannel,
        AnimationChannelTarget,
        AnimationSampler,
        Asset,
        Buffer,
        BufferView,
        Material,
        Mesh,
        Node,
        PbrMetallicRoughness,
        Primitive,
        Scene,
    )

    osim_path = Path(osim_path).expanduser().resolve()
    mot_path = Path(mot_path).expanduser().resolve()
    out_glb_path = Path(out_glb_path).expanduser().resolve()
    if not osim_path.is_file():
        raise FileNotFoundError(f"OSIM file not found: {osim_path}")
    if not mot_path.is_file():
        raise FileNotFoundError(f"IK MOT/STO file not found: {mot_path}")
    out_glb_path.parent.mkdir(parents=True, exist_ok=True)

    geometry_dirs = _resolve_geometry_dirs(osim_path, geom_dir)
    if geom_dir is not None and not Path(geom_dir).expanduser().resolve().is_dir():
        raise FileNotFoundError(f"Geometry directory not found: {geom_dir}")

    stride = max(1, int(stride))
    degree_to_rad = np.pi / 180.0

    model = osim.Model(str(osim_path))
    state = model.initSystem()
    if lift_pelvis_by:
        try:
            pelvis_ty = model.getCoordinateSet().get("pelvis_ty")
            pelvis_ty.setValue(state, pelvis_ty.getValue(state) + float(lift_pelvis_by))
        except Exception:
            pass

    in_degrees, all_times, labels, all_data = _read_mot_or_sto(mot_path, osim)
    mask = np.ones_like(all_times, dtype=bool)
    if t_start is not None:
        mask &= all_times >= float(t_start)
    if t_end is not None:
        mask &= all_times <= float(t_end)
    all_times = all_times[mask]
    all_data = all_data[mask]
    if len(all_times) == 0:
        raise ValueError("No frames remain after applying the selected time window.")

    frame_idx = np.arange(len(all_times))[::stride]
    times = all_times[frame_idx]
    data = all_data[frame_idx]
    if len(times) == 0:
        raise ValueError("No frames remain after applying stride.")

    mapping, unmatched_coordinates = _coordinate_mapping(model, labels, in_degrees=in_degrees)
    if not mapping:
        raise ValueError("None of the MOT/STO columns matched coordinates in the OpenSim model.")

    bodyset = model.getBodySet()
    body_names = [bodyset.get(i).getName() for i in range(bodyset.getSize())]
    name_to_body = {name.lower(): bodyset.get(i) for i, name in enumerate(body_names)}

    items = []
    missing_geometry = []
    for spec in _parse_geometry(osim_path):
        mesh_path = _find_geometry_file(spec["mesh_file"], geometry_dirs)
        if mesh_path is None:
            missing_geometry.append(spec["mesh_file"])
            continue
        frame = None
        frame_path = (spec.get("frame_path") or "").split("/")[-1].lower()
        if frame_path in name_to_body:
            frame = name_to_body[frame_path]
        elif spec.get("body_owner"):
            frame = name_to_body.get(str(spec["body_owner"]).lower())
        if frame is None:
            frame = _canonicalize_body_target(
                model,
                name_to_body,
                body_names,
                Path(spec["mesh_file"]).stem,
            )
        if skip_ground_fallbacks and frame == model.getGround():
            continue

        mesh = _load_polydata(
            mesh_path,
            pv,
            target_reduction=decimate_target_reduction,
            target_error=decimate_error,
            preserve_topology=decimate_preserve_topology,
        )
        scale = np.asarray(spec.get("scale") or (1.0, 1.0, 1.0), dtype=float)
        mesh.points *= scale[None, :]
        items.append(
            {
                "name": mesh_path.stem,
                "mesh": mesh,
                "loc": np.asarray(spec.get("local_translation") or (0.0, 0.0, 0.0), dtype=float),
                "rot": tuple(spec.get("local_rotation_deg") or (0.0, 0.0, 0.0)),
                "frame": frame,
                "mesh_path": str(mesh_path),
            }
        )

    if not items:
        raise ValueError(
            "No model geometry could be resolved. Pass `geom_dir=` pointing to the OpenSim "
            "Geometry folder or set `skip_ground_fallbacks=False` for diagnostic exports."
        )

    for item in items:
        item["local_R"] = _euler_deg_xyz_to_matrix(*item["rot"])
        item["local_p"] = item["loc"].astype(float)

    red, green, blue = _hex_to_rgb01(bone_hex)
    material = Material(
        name="Bones",
        pbrMetallicRoughness=PbrMetallicRoughness(
            baseColorFactor=[red, green, blue, float(opacity)],
            metallicFactor=0.0,
            roughnessFactor=1.0,
        ),
        alphaMode="BLEND" if opacity < 1.0 else "OPAQUE",
    )

    gltf = GLTF2()
    gltf.asset = Asset(version="2.0", generator="monomech")
    gltf.materials = [material]
    gltf.scenes = [Scene(nodes=[])]
    gltf.scene = 0
    gltf.meshes = []
    gltf.nodes = []
    gltf.bufferViews = []
    gltf.accessors = []

    binary = bytearray()

    def pad4() -> None:
        while len(binary) % 4 != 0:
            binary.extend(bytes((0,)))

    def add_accessor(array: np.ndarray, *, component_type: int, accessor_type: str, target=None):
        arr = np.ascontiguousarray(array)
        offset = len(binary)
        binary.extend(arr.tobytes())
        pad4()
        byte_length = arr.nbytes
        gltf.bufferViews.append(
            BufferView(buffer=0, byteOffset=offset, byteLength=byte_length, target=target)
        )
        buffer_view_idx = len(gltf.bufferViews) - 1
        accessor = Accessor(
            bufferView=buffer_view_idx,
            byteOffset=0,
            componentType=component_type,
            count=int(arr.shape[0]),
            type=accessor_type,
        )
        if accessor_type in {SCALAR, VEC3}:
            reshaped = np.asarray(arr).reshape(arr.shape[0], -1)
            accessor.min = reshaped.min(axis=0).astype(float).tolist()
            accessor.max = reshaped.max(axis=0).astype(float).tolist()
        gltf.accessors.append(accessor)
        return len(gltf.accessors) - 1

    for item in items:
        vertices = np.asarray(item["mesh"].points, dtype=np.float32)
        faces = item["mesh"].faces.reshape(-1, 4)[:, 1:].astype(np.uint32)
        position_accessor = add_accessor(
            vertices,
            component_type=FLOAT,
            accessor_type=VEC3,
            target=ARRAY_BUFFER,
        )
        index_accessor = add_accessor(
            faces.ravel(),
            component_type=UNSIGNED_INT,
            accessor_type=SCALAR,
            target=ELEMENT_ARRAY_BUFFER,
        )
        primitive = Primitive(
            attributes={"POSITION": position_accessor},
            indices=index_accessor,
            material=0,
        )
        gltf.meshes.append(Mesh(primitives=[primitive], name=f"mesh_{item['name']}"))
        mesh_idx = len(gltf.meshes) - 1
        gltf.nodes.append(Node(mesh=mesh_idx, name=f"node_{item['name']}"))
        gltf.scenes[0].nodes.append(len(gltf.nodes) - 1)

    times_f32 = np.asarray(times, dtype=np.float32)
    shared_time_accessor = add_accessor(
        times_f32,
        component_type=FLOAT,
        accessor_type=SCALAR,
    )

    nframes = len(times_f32)
    translation_tracks = [np.zeros((nframes, 3), dtype=np.float32) for _ in items]
    rotation_tracks = [np.zeros((nframes, 4), dtype=np.float32) for _ in items]

    marker_df = None
    marker_names = []
    marker_positions = None
    if return_markers:
        marker_set = model.getMarkerSet()
        marker_names = [marker_set.get(i).getName() for i in range(marker_set.getSize())]
        marker_positions = np.zeros((nframes, 3 * len(marker_names)), dtype=float)

    for frame_number, row in enumerate(data):
        for coord, col, convert_degrees in mapping:
            value = float(row[col])
            if convert_degrees:
                value *= degree_to_rad
            try:
                coord.setValue(state, value, True)
            except Exception:
                coord.setValue(state, value)
        model.realizePosition(state)

        if marker_positions is not None:
            marker_set = model.getMarkerSet()
            for marker_idx in range(marker_set.getSize()):
                marker = marker_set.get(marker_idx)
                marker_local = _simtk_vec3_to_np(marker.get_location())
                parent = marker.getParentFrame()
                parent_transform = parent.getTransformInGround(state)
                parent_r = _simtk_rot_to_np(parent_transform.R())
                marker_global = _simtk_vec3_to_np(parent_transform.p()) + parent_r @ marker_local
                marker_positions[
                    frame_number,
                    3 * marker_idx : 3 * marker_idx + 3,
                ] = marker_global

        for item_idx, item in enumerate(items):
            transform = item["frame"].getTransformInGround(state)
            frame_r = _simtk_rot_to_np(transform.R())
            frame_p = _simtk_vec3_to_np(transform.p())
            rotation = frame_r @ item["local_R"]
            translation = frame_p + frame_r @ item["local_p"]
            translation_tracks[item_idx][frame_number, :] = translation
            quat = _matrix_to_quat_xyzw(rotation)
            if (
                enforce_quat_continuity
                and frame_number > 0
                and np.dot(quat, rotation_tracks[item_idx][frame_number - 1]) < 0
            ):
                quat = -quat
            rotation_tracks[item_idx][frame_number, :] = quat

    if marker_positions is not None:
        columns = []
        for name in marker_names:
            columns.extend([f"{name}_x", f"{name}_y", f"{name}_z"])
        marker_df = pd.DataFrame(
            marker_positions,
            index=pd.Index(times, name="time"),
            columns=columns,
        )

    rot_tol_rad = None if thin_rot_tol_deg is None else float(thin_rot_tol_deg) * degree_to_rad
    origin_rot_tol_rad = (
        None if origin_rot_tol_deg is None else float(origin_rot_tol_deg) * degree_to_rad
    )

    animation = Animation(name="ik_motion", samplers=[], channels=[])
    kept_node_indices = []
    dropped_static_nodes = 0
    dropped_origin_nodes = 0

    tracks = zip(translation_tracks, rotation_tracks, strict=True)
    for node_idx, (translation, rotation) in enumerate(tracks):
        if drop_origin_nodes and _is_origin_node(
            translation,
            rotation,
            pos_tol=float(origin_pos_tol),
            rot_tol_rad=origin_rot_tol_rad,
        ):
            dropped_origin_nodes += 1
            continue

        if drop_static_nodes:
            max_translation_delta = float(
                np.linalg.norm(translation - translation[0], axis=1).max()
            )
            dots = np.abs(np.clip((rotation * rotation[0]).sum(axis=1), -1.0, 1.0))
            max_rotation_delta = float(2.0 * np.arccos(np.clip(dots.min(), -1.0, 1.0)))
            pos_static = thin_pos_tol is None or max_translation_delta <= thin_pos_tol
            rot_static = rot_tol_rad is None or max_rotation_delta <= rot_tol_rad
            if pos_static and rot_static:
                t_out = np.asarray([times_f32[0]], dtype=np.float32)
                translation_out = translation[:1]
                rotation_out = rotation[:1]
                dropped_static_nodes += 1
            else:
                t_out, translation_out, rotation_out = _thin_track(
                    times_f32,
                    translation,
                    rotation,
                    pos_tol=thin_pos_tol,
                    rot_tol_rad=rot_tol_rad,
                )
        elif thin_pos_tol is not None or rot_tol_rad is not None:
            t_out, translation_out, rotation_out = _thin_track(
                times_f32,
                translation,
                rotation,
                pos_tol=thin_pos_tol,
                rot_tol_rad=rot_tol_rad,
            )
        else:
            t_out = times_f32
            translation_out = translation
            rotation_out = rotation

        kept_node_indices.append(node_idx)
        if len(t_out) == len(times_f32) and np.allclose(t_out, times_f32):
            time_accessor = shared_time_accessor
        else:
            time_accessor = add_accessor(
                np.asarray(t_out, dtype=np.float32),
                component_type=FLOAT,
                accessor_type=SCALAR,
            )

        translation_accessor = add_accessor(
            np.asarray(translation_out, dtype=np.float32),
            component_type=FLOAT,
            accessor_type=VEC3,
        )
        animation.samplers.append(
            AnimationSampler(
                input=time_accessor,
                output=translation_accessor,
                interpolation="LINEAR",
            )
        )
        animation.channels.append(
            AnimationChannel(
                sampler=len(animation.samplers) - 1,
                target=AnimationChannelTarget(node=node_idx, path="translation"),
            )
        )

        rotation_accessor = add_accessor(
            np.asarray(rotation_out, dtype=np.float32),
            component_type=FLOAT,
            accessor_type=VEC4,
        )
        animation.samplers.append(
            AnimationSampler(
                input=time_accessor,
                output=rotation_accessor,
                interpolation="LINEAR",
            )
        )
        animation.channels.append(
            AnimationChannel(
                sampler=len(animation.samplers) - 1,
                target=AnimationChannelTarget(node=node_idx, path="rotation"),
            )
        )

    if drop_origin_nodes:
        keep = set(kept_node_indices)
        gltf.scenes[0].nodes = [node_idx for node_idx in gltf.scenes[0].nodes if node_idx in keep]

    id_summary = _id_metadata(id_path, osim)
    metadata = {
        "osim_path": str(osim_path),
        "mot_path": str(mot_path),
        "id_path": None if id_path is None else str(Path(id_path).expanduser().resolve()),
        "geometry_dirs": [str(path) for path in geometry_dirs],
        "mesh_count": len(items),
        "node_count": len(gltf.scenes[0].nodes),
        "source_frame_count": int(len(all_times)),
        "exported_frame_count": int(nframes),
        "stride": stride,
        "time_range": [float(times[0]), float(times[-1])],
        "unmatched_coordinates": unmatched_coordinates,
        "missing_geometry": missing_geometry,
        "dropped_static_nodes": dropped_static_nodes,
        "dropped_origin_nodes": dropped_origin_nodes,
        "id_summary": id_summary,
    }
    gltf.extras = {"monomech": metadata}
    gltf.animations = [animation]
    gltf.buffers = [Buffer(byteLength=len(binary))]
    gltf.set_binary_blob(bytes(binary))
    gltf.save_binary(str(out_glb_path))

    if not quiet:
        print(f"GLB saved: {out_glb_path}")
        print(
            "  nodes written: "
            f"{len(gltf.scenes[0].nodes)} / {len(gltf.nodes)} | "
            f"frames: {nframes} | stride: {stride}"
        )

    return OpenSimAnimationResult(
        glb_path=out_glb_path,
        marker_dataframe=marker_df,
        metadata=metadata,
    )


def save_ik_animation(
    osim_path: str | Path,
    geom_dir: str | Path,
    mot_path: str | Path,
    out_glb_path: str | Path,
    **kwargs,
) -> pd.DataFrame:
    """Backward-compatible wrapper for older notebook code.

    Returns the marker-position DataFrame, matching the prototype function.
    New code should prefer `save_opensim_animation()`, which returns an
    `OpenSimAnimationResult`.
    """

    result = save_opensim_animation(
        osim_path=osim_path,
        geom_dir=geom_dir,
        mot_path=mot_path,
        out_glb_path=out_glb_path,
        **kwargs,
    )
    return result.to_dataframe()


def save_animation_viewer(
    html_path: str | Path,
    glb_path: str | Path,
    *,
    title: str = "monomech OpenSim animation",
) -> Path:
    """Write a small self-contained HTML viewer for a GLB animation."""

    html_path = Path(html_path).expanduser().resolve()
    glb_path = Path(glb_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    rel_glb = glb_path.as_posix()
    if glb_path.is_absolute():
        try:
            rel_glb = glb_path.resolve().relative_to(html_path.parent).as_posix()
        except ValueError:
            rel_glb = glb_path.resolve().as_uri()

    payload = json.dumps({"title": title, "glb": rel_glb})
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    html, body {{ height: 100%; margin: 0; background: #f7f8fb; color: #1e252b; }}
    body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; }}
    model-viewer {{ width: 100%; height: 100%; background: #f7f8fb; }}
    .bar {{ position: fixed; top: 0; left: 0; right: 0; z-index: 2; padding: 10px 14px;
      background: rgba(255,255,255,.86); border-bottom: 1px solid rgba(20,20,20,.12); }}
  </style>
  <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.5.0/model-viewer.min.js"></script>
</head>
<body>
  <div class="bar">{title}</div>
  <model-viewer id="viewer" src="{rel_glb}" camera-controls autoplay animation-name="ik_motion"
    shadow-intensity="0.35" exposure="1.0"></model-viewer>
  <script type="application/json" id="monomech-viewer">{payload}</script>
</body>
</html>
"""
    html_path.write_text(html, encoding="utf-8", newline="\n")
    return html_path


def _storage_for_visualizer(path: str | Path | None, *, max_columns: int = 14) -> dict[str, Any] | None:
    if path is None:
        return None
    from .io.storage import read_storage

    storage_path = Path(path).expanduser().resolve()
    if not storage_path.is_file():
        raise FileNotFoundError(f"Storage file not found: {storage_path}")
    df = read_storage(storage_path)
    if df.empty:
        return {"path": str(storage_path), "columns": [], "time": [], "series": {}}
    time_col = "time" if "time" in df.columns else df.columns[0]
    time = pd.to_numeric(df[time_col], errors="coerce").to_numpy(dtype=float)
    numeric_cols = []
    for col in df.columns:
        if col == time_col:
            continue
        values = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        if len(finite) == 0:
            continue
        score = float(np.nanpercentile(np.abs(finite), 95))
        numeric_cols.append((col, score, values))
    numeric_cols.sort(key=lambda item: item[1], reverse=True)
    selected = numeric_cols[:max_columns]
    return {
        "path": str(storage_path),
        "columns": [name for name, _, _ in selected],
        "time": np.round(time, 5).tolist(),
        "series": {name: np.round(values, 6).tolist() for name, _, values in selected},
    }


def _marker_payload(marker_df: pd.DataFrame, *, max_frames: int) -> dict[str, Any]:
    if marker_df.empty:
        return {"names": [], "time": [], "frames": [], "segments": []}
    marker_names = sorted({col[:-2] for col in marker_df.columns if col.endswith("_x")})
    if not marker_names:
        return {"names": [], "time": [], "frames": [], "segments": []}
    sample = np.linspace(0, len(marker_df) - 1, min(max_frames, len(marker_df)), dtype=int)
    sample = np.unique(sample)
    sampled = marker_df.iloc[sample]
    frames = []
    for _, row in sampled.iterrows():
        frame = []
        for name in marker_names:
            frame.append(
                [
                    float(row.get(f"{name}_x", np.nan)),
                    float(row.get(f"{name}_y", np.nan)),
                    float(row.get(f"{name}_z", np.nan)),
                ]
            )
        frames.append(frame)
    segments = _infer_marker_segments(marker_names)
    return {
        "names": marker_names,
        "time": np.round(sampled.index.to_numpy(dtype=float), 5).tolist(),
        "frames": frames,
        "segments": segments,
    }


def _infer_marker_segments(marker_names: list[str]) -> list[list[int]]:
    norm = {re.sub(r"[^a-z0-9]", "", name.lower()): i for i, name in enumerate(marker_names)}

    def find(*needles: str) -> int | None:
        for key, idx in norm.items():
            if all(needle in key for needle in needles):
                return idx
        return None

    pairs = [
        (find("pelvis"), find("torso")),
        (find("hip", "r"), find("knee", "r")),
        (find("knee", "r"), find("ankle", "r")),
        (find("ankle", "r"), find("toe", "r")),
        (find("hip", "l"), find("knee", "l")),
        (find("knee", "l"), find("ankle", "l")),
        (find("ankle", "l"), find("toe", "l")),
        (find("shoulder", "r"), find("elbow", "r")),
        (find("elbow", "r"), find("wrist", "r")),
        (find("shoulder", "l"), find("elbow", "l")),
        (find("elbow", "l"), find("wrist", "l")),
        (find("shoulder", "r"), find("shoulder", "l")),
        (find("hip", "r"), find("hip", "l")),
        (find("neck"), find("head")),
    ]
    out = []
    seen = set()
    for a, b in pairs:
        if a is None or b is None or a == b:
            continue
        key = tuple(sorted((a, b)))
        if key not in seen:
            out.append([a, b])
            seen.add(key)
    return out


def _external_load_payload(path: str | Path | None, *, target_time: list[float]) -> dict[str, Any] | None:
    if path is None:
        return None
    from .io.storage import read_storage

    force_path = Path(path).expanduser().resolve()
    if not force_path.is_file():
        raise FileNotFoundError(f"External-load MOT file not found: {force_path}")
    df = read_storage(force_path)
    if df.empty or "time" not in df.columns:
        return None
    src_t = pd.to_numeric(df["time"], errors="coerce").to_numpy(dtype=float)
    load_names = sorted(
        {
            col[:-3]
            for col in df.columns
            if col.endswith("_vx") and f"{col[:-3]}_px" in df.columns
        }
    )
    frames = []
    target = np.asarray(target_time, dtype=float)
    for t in target:
        frame = []
        for name in load_names:
            values = {}
            for suffix in ("vx", "vy", "vz", "px", "py", "pz"):
                col = f"{name}_{suffix}"
                y = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
                arr = y.fillna(0.0).to_numpy(dtype=float)
                values[suffix] = float(np.interp(t, src_t, arr, left=0.0, right=0.0))
            frame.append(
                {
                    "name": name,
                    "point": [values["px"], values["py"], values["pz"]],
                    "force": [values["vx"], values["vy"], values["vz"]],
                }
            )
        frames.append(frame)
    return {"path": str(force_path), "names": load_names, "frames": frames}


def _write_visualizer_html(
    html_path: Path,
    *,
    title: str,
    payload: dict[str, Any],
) -> Path:
    html_path.parent.mkdir(parents=True, exist_ok=True)
    payload_json = json.dumps(_json_safe(payload), allow_nan=False)
    safe_title = escape(title)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.5.0/model-viewer.min.js"></script>
  <style>
    :root {{ --ink:#15201d; --muted:#63716e; --line:#d7dfdd; --panel:#fff; --bg:#f4f7f6; --accent:#0f766e; --force:#d65a31; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; background:var(--bg); color:var(--ink); }}
    header {{ padding:18px 22px; border-bottom:1px solid var(--line); background:rgba(255,255,255,.92); position:sticky; top:0; z-index:5; backdrop-filter:blur(12px); }}
    h1 {{ margin:0; font-size:22px; letter-spacing:0; }}
    .sub {{ color:var(--muted); margin-top:4px; font-size:13px; }}
    main {{ display:grid; grid-template-columns:minmax(420px, 1.25fr) minmax(360px, .75fr); gap:14px; padding:14px; }}
    section {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
    .panel-title {{ padding:10px 12px; border-bottom:1px solid var(--line); font-weight:750; font-size:13px; display:flex; justify-content:space-between; gap:10px; align-items:center; }}
    #scene {{ height:620px; }}
    #glbPanel {{ display:none; height:620px; }}
    model-viewer {{ width:100%; height:100%; background:#f8faf9; }}
    .controls {{ display:flex; align-items:center; gap:10px; padding:10px 12px; border-top:1px solid var(--line); background:#fbfcfc; }}
    button, select {{ border:1px solid var(--line); background:white; border-radius:6px; padding:7px 10px; font:inherit; }}
    button {{ cursor:pointer; font-weight:700; color:var(--accent); }}
    input[type=range] {{ flex:1; accent-color:var(--accent); }}
    .stack {{ display:grid; gap:14px; }}
    .plot {{ height:265px; }}
    .stats {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; padding:10px; }}
    .stat {{ border:1px solid var(--line); border-radius:8px; padding:9px; background:#fbfcfc; }}
    .stat b {{ display:block; font-size:18px; }}
    .stat span {{ color:var(--muted); font-size:12px; }}
    .tabs {{ display:flex; gap:6px; padding:8px; border-bottom:1px solid var(--line); background:#fbfcfc; }}
    .tab.active {{ background:var(--accent); color:white; border-color:var(--accent); }}
    @media (max-width: 980px) {{ main {{ grid-template-columns:1fr; }} #scene, #glbPanel {{ height:520px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{safe_title}</h1>
    <div class="sub">Synchronized 3D markers, external-force arrows, IK coordinates, and inverse-dynamics traces.</div>
  </header>
  <main>
    <section>
      <div class="tabs">
        <button class="tab active" data-view="plotly">3D markers + forces</button>
        <button class="tab" data-view="glb" id="glbTab">GLB model</button>
      </div>
      <div id="scene"></div>
      <div id="glbPanel"><model-viewer id="glbViewer" camera-controls autoplay shadow-intensity="0.4" exposure="1.0"></model-viewer></div>
      <div class="controls">
        <button id="play">Play</button>
        <input id="scrub" type="range" min="0" max="0" value="0">
        <span id="time">0.000 s</span>
      </div>
    </section>
    <div class="stack">
      <section>
        <div class="panel-title">Run Summary</div>
        <div class="stats" id="stats"></div>
      </section>
      <section>
        <div class="panel-title">IK Coordinates <select id="ikSelect"></select></div>
        <div id="ikPlot" class="plot"></div>
      </section>
      <section>
        <div class="panel-title">Inverse Dynamics <select id="idSelect"></select></div>
        <div id="idPlot" class="plot"></div>
      </section>
    </div>
  </main>
  <script id="payload" type="application/json">{payload_json}</script>
  <script>
    const data = JSON.parse(document.getElementById('payload').textContent);
    const marker = data.markers || {{names:[], time:[], frames:[], segments:[]}};
    const force = data.forces || {{names:[], frames:[]}};
    const scrub = document.getElementById('scrub');
    const timeLabel = document.getElementById('time');
    const playBtn = document.getElementById('play');
    let idx = 0, timer = null;
    scrub.max = Math.max(0, marker.frames.length - 1);

    document.getElementById('stats').innerHTML = [
      ['Frames', marker.frames.length],
      ['Markers', marker.names.length],
      ['Forces', (force.names || []).length],
      ['IK traces', data.ik?.columns?.length || 0],
      ['ID traces', data.id?.columns?.length || 0],
      ['Duration', marker.time.length ? (marker.time[marker.time.length-1]-marker.time[0]).toFixed(3)+' s' : '0 s']
    ].map(([k,v]) => `<div class="stat"><b>${{v}}</b><span>${{k}}</span></div>`).join('');

    function frameArrays(i) {{
      const f = marker.frames[i] || [];
      return {{x:f.map(p=>p[0]), y:f.map(p=>p[1]), z:f.map(p=>p[2])}};
    }}
    function segmentArrays(i) {{
      const f = marker.frames[i] || [];
      const xs=[], ys=[], zs=[];
      for (const [a,b] of marker.segments || []) {{
        if (!f[a] || !f[b]) continue;
        xs.push(f[a][0], f[b][0], null); ys.push(f[a][1], f[b][1], null); zs.push(f[a][2], f[b][2], null);
      }}
      return {{x:xs,y:ys,z:zs}};
    }}
    function forceArrays(i) {{
      const frames = force.frames || [];
      const loads = frames[i] || [];
      let maxMag = 0;
      for (const l of loads) maxMag = Math.max(maxMag, Math.hypot(...l.force));
      const scale = maxMag > 0 ? (data.force_scale || 0.35) / maxMag : 1;
      const xs=[], ys=[], zs=[], text=[];
      for (const l of loads) {{
        const p=l.point, v=l.force.map(x=>x*scale);
        xs.push(p[0], p[0]+v[0], null); ys.push(p[1], p[1]+v[1], null); zs.push(p[2], p[2]+v[2], null);
        text.push(l.name, l.name, '');
      }}
      return {{x:xs,y:ys,z:zs,text}};
    }}
    const p0 = frameArrays(0), s0 = segmentArrays(0), f0 = forceArrays(0);
    Plotly.newPlot('scene', [
      {{type:'scatter3d', mode:'markers', name:'markers', x:p0.x, y:p0.y, z:p0.z, text:marker.names, hoverinfo:'text', marker:{{size:4,color:'#0f766e'}}}},
      {{type:'scatter3d', mode:'lines', name:'skeleton', x:s0.x, y:s0.y, z:s0.z, line:{{width:5,color:'#24302d'}}, hoverinfo:'skip'}},
      {{type:'scatter3d', mode:'lines+markers', name:'external forces', x:f0.x, y:f0.y, z:f0.z, text:f0.text, line:{{width:8,color:'#d65a31'}}, marker:{{size:3,color:'#d65a31'}}}}
    ], {{
      margin:{{l:0,r:0,b:0,t:0}},
      scene:{{aspectmode:'data', xaxis:{{title:'X'}}, yaxis:{{title:'Y'}}, zaxis:{{title:'Z'}}}},
      legend:{{orientation:'h', x:0.02, y:0.98}}
    }}, {{responsive:true}});

    function updateFrame(i) {{
      idx = Math.max(0, Math.min(marker.frames.length - 1, i));
      const p = frameArrays(idx), s = segmentArrays(idx), f = forceArrays(idx);
      Plotly.restyle('scene', {{x:[p.x], y:[p.y], z:[p.z]}}, [0]);
      Plotly.restyle('scene', {{x:[s.x], y:[s.y], z:[s.z]}}, [1]);
      Plotly.restyle('scene', {{x:[f.x], y:[f.y], z:[f.z], text:[f.text]}}, [2]);
      scrub.value = idx;
      timeLabel.textContent = (marker.time[idx] || 0).toFixed(3) + ' s';
    }}
    scrub.addEventListener('input', e => updateFrame(Number(e.target.value)));
    playBtn.addEventListener('click', () => {{
      if (timer) {{ clearInterval(timer); timer=null; playBtn.textContent='Play'; return; }}
      playBtn.textContent='Pause';
      timer = setInterval(() => {{ updateFrame((idx + 1) % marker.frames.length); }}, 45);
    }});

    function makeSeriesPlot(div, store, selectId, color) {{
      const select = document.getElementById(selectId);
      const cols = store?.columns || [];
      select.innerHTML = cols.map(c => `<option value="${{c}}">${{c}}</option>`).join('');
      function draw() {{
        const col = select.value || cols[0];
        const y = store?.series?.[col] || [];
        Plotly.newPlot(div, [{{type:'scatter', mode:'lines', x:store?.time || [], y, line:{{color, width:2}}, name:col}}], {{
          margin:{{l:44,r:12,b:34,t:8}}, xaxis:{{title:'time (s)'}}, yaxis:{{title:col}}, paper_bgcolor:'white', plot_bgcolor:'white'
        }}, {{responsive:true}});
      }}
      select.addEventListener('change', draw); draw();
    }}
    makeSeriesPlot('ikPlot', data.ik, 'ikSelect', '#0f766e');
    makeSeriesPlot('idPlot', data.id, 'idSelect', '#d65a31');

    const glbTab = document.getElementById('glbTab');
    if (data.glb_path) {{
      document.getElementById('glbViewer').src = data.glb_path;
    }} else {{
      glbTab.disabled = true; glbTab.textContent = 'GLB model unavailable';
    }}
    document.querySelectorAll('.tab').forEach(btn => btn.addEventListener('click', () => {{
      if (btn.disabled) return;
      document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const glb = btn.dataset.view === 'glb';
      document.getElementById('scene').style.display = glb ? 'none' : 'block';
      document.getElementById('glbPanel').style.display = glb ? 'block' : 'none';
    }}));
  </script>
</body>
</html>
"""
    html_path.write_text(html, encoding="utf-8", newline="\n")
    return html_path


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    return value


def save_opensim_visualizer(
    html_path: str | Path,
    *,
    osim_path: str | Path | None = None,
    ik_path: str | Path | None = None,
    id_path: str | Path | None = None,
    external_loads_path: str | Path | None = None,
    glb_path: str | Path | None = None,
    marker_dataframe: pd.DataFrame | None = None,
    title: str = "monomech IK and ID visualizer",
    max_frames: int = 240,
    marker_stride: int = 1,
) -> OpenSimVisualizerResult:
    """Write a notebook-ready HTML dashboard for IK, ID, forces, and 3D motion."""

    html_path = Path(html_path).expanduser().resolve()
    if marker_dataframe is None:
        if osim_path is None or ik_path is None:
            raise ValueError("Provide marker_dataframe or both osim_path and ik_path.")
        marker_dataframe = extract_opensim_marker_positions(
            osim_path=osim_path,
            mot_path=ik_path,
            stride=marker_stride,
        )
    markers = _marker_payload(marker_dataframe, max_frames=max_frames)
    forces = _external_load_payload(external_loads_path, target_time=markers["time"])

    glb_ref = None
    if glb_path is not None:
        glb = Path(glb_path).expanduser().resolve()
        if glb.is_file():
            try:
                glb_ref = glb.relative_to(html_path.parent).as_posix()
            except ValueError:
                glb_ref = glb.as_uri()

    payload = {
        "title": title,
        "markers": markers,
        "forces": forces,
        "ik": _storage_for_visualizer(ik_path),
        "id": _storage_for_visualizer(id_path),
        "glb_path": glb_ref,
        "force_scale": 0.35,
    }
    _write_visualizer_html(html_path, title=title, payload=payload)
    metadata = {
        "html_path": str(html_path),
        "glb_path": glb_ref,
        "marker_frames": len(markers["frames"]),
        "marker_count": len(markers["names"]),
        "force_count": 0 if forces is None else len(forces["names"]),
        "ik_path": None if ik_path is None else str(Path(ik_path).expanduser().resolve()),
        "id_path": None if id_path is None else str(Path(id_path).expanduser().resolve()),
        "external_loads_path": None
        if external_loads_path is None
        else str(Path(external_loads_path).expanduser().resolve()),
    }
    return OpenSimVisualizerResult(html_path=html_path, metadata=metadata)


def show_ik_animation(html_path: str | Path, glb_path: str | Path) -> Path:
    """Compatibility helper that writes an HTML viewer for an IK animation."""

    return save_animation_viewer(html_path, glb_path)
