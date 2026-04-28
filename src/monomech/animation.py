# ruff: noqa: E501

from __future__ import annotations

import base64
import io
import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

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
    marker_dataframe: pd.DataFrame | None = None

    def _repr_html_(self) -> str:
        uri = _notebook_file_url(self.html_path)
        return (
            f'<iframe src="{uri}" width="100%" height="860" '
            'style="border:0;border-radius:8px;overflow:hidden;"></iframe>'
        )

    def display(self, *, width: str = "100%", height: int = 860, inline_glb: bool = False):
        """Display this visualizer in a Jupyter notebook."""

        return display_visualizer(self, width=width, height=height, inline_glb=inline_glb)

    def show(self, *, width: str = "100%", height: int = 860, inline_glb: bool = False):
        """Alias for `display()` in notebooks."""

        return self.display(width=width, height=height, inline_glb=inline_glb)

    def to_dataframe(self) -> pd.DataFrame:
        """Return model marker positions used by the visualizer, when available."""

        if self.marker_dataframe is None:
            return pd.DataFrame()
        return self.marker_dataframe.copy()


def display_visualizer(
    target: Any,
    *,
    width: str = "100%",
    height: int = 860,
    inline_glb: bool = False,
):
    """Display a monomech visualizer from a path or pipeline result in Jupyter."""

    html_path = None
    metadata = {}
    if isinstance(target, OpenSimVisualizerResult):
        html_path = target.html_path
        metadata = target.metadata
    elif hasattr(target, "visualizer") and target.visualizer is not None:
        html_path = target.visualizer.html_path
        metadata = getattr(target.visualizer, "metadata", {}) or {}
    else:
        html_path = Path(target)

    try:
        from IPython.display import HTML, IFrame, display
    except Exception as exc:
        raise ImportError("Install `monomech[notebook]` to display visualizers in Jupyter.") from exc

    if inline_glb or _running_in_colab():
        html = _inline_notebook_visualizer_html(html_path, metadata, width=width, height=height)
        frame = HTML(html)
        display(frame)
        return frame

    frame = IFrame(_notebook_file_url(html_path), width=width, height=height)
    display(frame)
    return frame


def _running_in_colab() -> bool:
    try:
        import google.colab  # type: ignore  # noqa: F401
    except Exception:
        return False
    return True


def _notebook_file_url(path: str | Path) -> str:
    resolved = Path(path).expanduser().resolve()
    try:
        rel = resolved.relative_to(Path.cwd().resolve())
        return "/files/" + quote(rel.as_posix())
    except ValueError:
        return resolved.as_uri()


def _inline_notebook_visualizer_html(
    html_path: str | Path,
    metadata: dict[str, Any] | None = None,
    *,
    width: str = "100%",
    height: int = 860,
) -> str:
    html_path = Path(html_path).expanduser().resolve()
    html = html_path.read_text(encoding="utf-8")
    glb_path = None
    if metadata:
        glb_path = metadata.get("glb_path")
    if glb_path:
        glb = Path(glb_path).expanduser().resolve()
        if glb.is_file():
            b64 = base64.b64encode(glb.read_bytes()).decode("ascii")
            html = _inject_glb_base64_autoload(html, b64)
    sizing = (
        f"<style>html,body{{width:{escape(str(width))};"
        f"height:{int(height)}px;min-height:{int(height)}px;}}</style>"
    )
    return html.replace("</head>", sizing + "</head>", 1)


def _inject_glb_base64_autoload(html: str, b64: str) -> str:
    match = re.search(
        r'(<script[^>]*type=["\']module["\'][^>]*>)(.*?)(</script>)',
        html,
        flags=re.I | re.S,
    )
    if not match:
        return html
    start_tag, module_code, end_tag = match.groups()
    module_code = module_code.replace(
        "if (data.glb_path) loadGlb(data.glb_path);",
        "if (!window.MONOMECH_GLB_BASE64 && data.glb_path) loadGlb(data.glb_path);",
    )
    inject_global = '<script>window.MONOMECH_GLB_BASE64="__GLB_B64__";</script>'
    autoload_js = r"""

// ---- Auto-load GLB injected by monomech notebook display ----
try {
  if (window.MONOMECH_GLB_BASE64) {
    const binary = atob(window.MONOMECH_GLB_BASE64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const blob = new Blob([bytes], { type: "model/gltf-binary" });
    const url = URL.createObjectURL(blob);
    if (typeof loadGlb === "function") {
      loadGlb(url);
    } else {
      console.error("monomech notebook display could not find loadGlb().");
    }
  }
} catch (error) {
  console.error("monomech notebook GLB autoload error:", error);
}
"""
    patched = (
        html[: match.start()]
        + inject_global
        + start_tag
        + module_code
        + autoload_js
        + end_tag
        + html[match.end() :]
    )
    return patched.replace("__GLB_B64__", b64)


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
    return _dedupe_geometry_specs(specs)


def _dedupe_geometry_specs(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    body_owned_meshes = {spec["mesh_file"] for spec in specs if spec.get("body_owner")}
    out: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None, str, tuple[float, ...] | None]] = set()
    for spec in specs:
        if (
            spec.get("body_owner") is None
            and spec.get("frame_path") is None
            and spec["mesh_file"] in body_owned_meshes
        ):
            continue
        scale = spec.get("scale")
        key = (
            spec.get("body_owner"),
            spec.get("frame_path"),
            spec["mesh_file"],
            None if scale is None else tuple(float(v) for v in scale),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(spec)
    return out


def _resolve_geometry_dirs(osim_path: Path, geom_dir: str | Path | None) -> list[Path]:
    candidates: list[Path] = []
    if geom_dir is not None:
        candidates.append(Path(geom_dir).expanduser().resolve())
    else:
        try:
            from .resources import get_builtin_geometry_dir

            candidates.append(get_builtin_geometry_dir())
        except Exception:
            pass
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
    alias_names = _geometry_file_aliases(mesh_path.name)
    if not mesh_path.is_absolute():
        candidates.extend([directory / mesh_file for directory in geometry_dirs])
        candidates.extend([directory / mesh_path.name for directory in geometry_dirs])
        for alias in alias_names:
            candidates.extend([directory / alias for directory in geometry_dirs])
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except Exception:
            continue
        if resolved.is_file():
            return resolved
    return None


def _is_alias_resolution(mesh_file: str, resolved_path: Path) -> bool:
    return Path(mesh_file).name.lower() != resolved_path.name.lower()


def _geometry_spec_export_priority(spec: dict[str, Any]) -> tuple[int, str]:
    mesh_name = Path(str(spec.get("mesh_file", ""))).stem.lower()
    body = str(spec.get("body_owner") or "").lower()
    if mesh_name.startswith(("thoracic", "cerv")) or body == "torso":
        return (0, mesh_name)
    if mesh_name.startswith("lumbar"):
        return (20, mesh_name)
    return (10, mesh_name)


def _geometry_file_aliases(filename: str) -> list[str]:
    """Return common OpenSim geometry filename variants for full-body models."""

    stem = Path(filename).stem
    suffix = Path(filename).suffix or ".vtp"
    lower = stem.lower()
    aliases: list[str] = []

    def add(name: str) -> None:
        full = f"{name}{suffix}"
        if full != filename and full not in aliases:
            aliases.append(full)

    side_swap = re.match(r"^(?P<root>.+)_(?P<side>[rl])v?s?$", lower)
    if side_swap:
        root = side_swap.group("root")
        side = side_swap.group("side")
        add(f"{side}_{root}")
        add(f"{side}_{root}_SOMEINVERTEDFACES")

    prefix_swap = re.match(r"^(?P<side>[rl])_(?P<root>.+)$", lower)
    if prefix_swap:
        root = prefix_swap.group("root")
        side = prefix_swap.group("side")
        add(f"{root}_{side}")
        add(f"{root}_{side}v")

    if lower == "foot":
        add("r_foot")
    elif lower == "bofoot":
        add("r_bofoot")
    elif lower.startswith(("lumbar", "thoracic", "cerv")):
        add("hat_spine")
    elif lower.startswith("talus_"):
        side = "r" if "_r" in lower else "l" if "_l" in lower else ""
        if side:
            add(f"{side}_talus")

    return aliases


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
    if re.search(r"(^|_)(r|right)(v|vs|s)?($|_)", stem_lower) or stem_lower.endswith("right"):
        side = "r"
    elif (
        re.search(r"(^|_)(l|left)(v|vs|s)?($|_)", stem_lower)
        or stem_lower.endswith("left")
        or stem_lower.startswith("l_")
    ):
        side = "l"
    suffix = f"_{side}" if side else ""

    normalized = re.sub(r"(^|_)(r|l)(v|vs|s)($|_)", lambda m: f"{m.group(1)}{m.group(2)}{m.group(4)}", stem_lower)
    normalized = normalized.replace("_s", "").replace("sm", "")

    if "foot" in stem_lower or "bofoot" in stem_lower:
        for candidate in (f"calcn{suffix}", f"toes{suffix}", f"talus{suffix}", f"foot{suffix}"):
            if candidate.lower() in name_to_body:
                return name_to_body[candidate.lower()]

    if "hat_skull" in stem_lower or "skull" in stem_lower or "jaw" in stem_lower:
        if "head" in name_to_body:
            return name_to_body["head"]
    if "hat_ribs" in stem_lower or "scap" in stem_lower:
        if "torso" in name_to_body:
            return name_to_body["torso"]

    hand_parts = (
        "pisiform",
        "lunate",
        "scaphoid",
        "triquetrum",
        "hamate",
        "capitate",
        "trapezoid",
        "trapezium",
        "metacarpal",
        "index_",
        "middle_",
        "ring_",
        "little_",
        "thumb_",
    )
    if any(part in stem_lower for part in hand_parts):
        candidate = f"hand{suffix}"
        if candidate.lower() in name_to_body:
            return name_to_body[candidate.lower()]

    for root in (
        "patella",
        "fibula",
        "tibia",
        "femur",
        "talus",
        "humerus",
        "ulna",
        "radius",
    ):
        if root in stem_lower:
            candidate = f"{root}{suffix}"
            if candidate.lower() in name_to_body:
                return name_to_body[candidate.lower()]

    for candidate in ("pelvis", "sacrum"):
        if candidate in stem_lower and candidate in name_to_body:
            return name_to_body[candidate]

    for candidate in ("lumbar5", "lumbar4", "lumbar3", "lumbar2", "lumbar1"):
        if candidate in stem_lower and candidate in name_to_body:
            return name_to_body[candidate]
    if "thoracic" in stem_lower and "torso" in name_to_body:
        return name_to_body["torso"]

    matches = [
        (body_name, len(body_name))
        for body_name in body_names
        if body_name.lower() in stem_lower
        or body_name.lower() in normalized
        or normalized in body_name.lower()
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
    external_loads_path: str | Path | None = None,
    bone_hex: str = "#2b2f36",
    opacity: float = 1.0,
    skip_ground_fallbacks: bool = True,
    lift_pelvis_by: float = 0.0,
    t_start: float | None = None,
    t_end: float | None = None,
    stride: int = 1,
    thin_pos_tol: float | None = 1e-4,
    thin_rot_tol_deg: float | None = 0.05,
    drop_static_nodes: bool = False,
    decimate_target_reduction: float | None = None,
    decimate_error: float | None = None,
    decimate_preserve_topology: bool = False,
    enforce_quat_continuity: bool = True,
    drop_origin_nodes: bool = False,
    origin_pos_tol: float = 1e-5,
    origin_rot_tol_deg: float | None = None,
    return_markers: bool = True,
    quiet: bool = False,
) -> OpenSimAnimationResult:
    """Export an animated OpenSim model to a single binary glTF/GLB file.

    The animation is driven by IK coordinates from `mot_path`. If `id_path` or
    `external_loads_path` are provided, complete synchronized plotting and
    force-arrow data are embedded in the GLB extras for the online visualizer.
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
    for geometry_dir in geometry_dirs:
        try:
            osim.ModelVisualizer.addDirToGeometrySearchPaths(str(geometry_dir))
        except Exception:
            pass

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
    alias_resolutions: set[Path] = set()
    duplicate_alias_geometry = []
    for spec in sorted(_parse_geometry(osim_path), key=_geometry_spec_export_priority):
        mesh_path = _find_geometry_file(spec["mesh_file"], geometry_dirs)
        if mesh_path is None:
            missing_geometry.append(spec["mesh_file"])
            continue
        if _is_alias_resolution(spec["mesh_file"], mesh_path):
            resolved = mesh_path.resolve()
            if resolved in alias_resolutions:
                duplicate_alias_geometry.append(spec["mesh_file"])
                continue
            alias_resolutions.add(resolved)
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
    visualizer_payload = None
    if marker_df is not None:
        marker_payload = _marker_payload(marker_df, max_frames=len(marker_df))
        visualizer_payload = {
            "title": "monomech IK and ID visualizer",
            "markers": marker_payload,
            "bodies": _body_transform_payload(
                osim_path=osim_path,
                ik_path=mot_path,
                target_time=marker_payload["time"],
            ),
            "forces": _external_load_payload(
                external_loads_path,
                target_time=marker_payload["time"],
                osim_path=osim_path,
                ik_path=mot_path,
            ),
            "ik": _storage_for_visualizer(mot_path),
            "id": _storage_for_visualizer(id_path),
            "glb_path": None,
            "force_scale": 0.35,
        }
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
        "missing_geometry": sorted(set(missing_geometry)),
        "duplicate_alias_geometry": sorted(set(duplicate_alias_geometry)),
        "dropped_static_nodes": dropped_static_nodes,
        "dropped_origin_nodes": dropped_origin_nodes,
        "id_summary": id_summary,
        "visualizer": visualizer_payload,
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
    embed_glb: bool = False,
) -> Path:
    """Write a small Three.js HTML viewer for a GLB animation."""

    html_path = Path(html_path).expanduser().resolve()
    glb_path = Path(glb_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    glb_ref = _asset_reference(glb_path, html_path.parent, embed=embed_glb)
    payload = {"title": title, "glb_path": glb_ref}
    _write_simple_glb_viewer_html(html_path, title=title, payload=payload)
    return html_path


def create_glb_viewer(
    glb_path: str | Path | None = None,
    html_path: str | Path | None = None,
    *,
    title: str = "monomech IK and ID visualizer",
    embed_glb: bool = False,
) -> OpenSimVisualizerResult:
    """Create the production monomech GLB viewer.

    Pass a GLB path to preconfigure the viewer, or omit it to create the same
    empty upload-first viewer used on the documentation site.
    """

    glb = None
    if glb_path is not None:
        glb = Path(glb_path).expanduser().resolve()
        if not glb.is_file():
            raise FileNotFoundError(f"GLB file not found: {glb}")
    if html_path is None:
        if glb is None:
            html_path = Path("outputs") / "visualizer" / "glb_viewer.html"
        else:
            html_path = glb.with_suffix(".viewer.html")
    html_path = Path(html_path).expanduser().resolve()
    glb_ref = None
    if glb is not None:
        glb_ref = _asset_reference(glb, html_path.parent, embed=embed_glb)
    payload = _empty_visualizer_payload(title=title, glb_path=glb_ref)
    _write_visualizer_html(html_path, title=title, payload=payload)
    return OpenSimVisualizerResult(
        html_path=html_path,
        metadata={
            "html_path": str(html_path),
            "glb_path": None if glb is None else str(glb),
            "embedded_glb": bool(embed_glb and glb is not None),
            "viewer_kind": "glb",
        },
    )


def glb_viewer(
    glb_path: str | Path | None = None,
    html_path: str | Path | None = None,
    *,
    title: str = "monomech IK and ID visualizer",
    embed_glb: bool = False,
) -> OpenSimVisualizerResult:
    """One-line GLB viewer helper.

    `mm.glb_viewer().show()` opens the upload-first viewer. Passing a GLB path
    preloads that file when the browser can access it, or can be paired with
    `.show(inline_glb=True)` in notebooks.
    """

    return create_glb_viewer(
        glb_path=glb_path,
        html_path=html_path,
        title=title,
        embed_glb=embed_glb,
    )


def _empty_visualizer_payload(
    *,
    title: str = "monomech IK and ID visualizer",
    glb_path: str | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "markers": {"names": [], "time": [], "frames": [], "segments": []},
        "bodies": {"names": [], "time": [], "frames": [], "segments": []},
        "forces": None,
        "ik": {"path": None, "columns": [], "time": [], "series": {}},
        "id": {"path": None, "columns": [], "time": [], "series": {}},
        "glb_path": glb_path,
        "force_scale": 0.35,
    }


def _asset_reference(path: Path, relative_to: Path, *, embed: bool = False) -> str:
    resolved = path.expanduser().resolve() if path.is_absolute() else (relative_to / path).resolve()
    if embed and resolved.is_file() and resolved.suffix.lower() == ".glb":
        encoded = base64.b64encode(resolved.read_bytes()).decode("ascii")
        return f"data:model/gltf-binary;base64,{encoded}"
    ref = path.as_posix()
    if path.is_absolute():
        try:
            ref = resolved.relative_to(relative_to).as_posix()
        except ValueError:
            ref = resolved.as_uri()
    return ref


def _write_simple_glb_viewer_html(html_path: Path, *, title: str, payload: dict[str, Any]) -> Path:
    safe_title = escape(title)
    payload_json = json.dumps(_json_safe(payload), allow_nan=False)
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <style>
    :root { --ink:#17211e; --muted:#66736f; --line:#d9e2df; --accent:#0f766e; --bg:#f5f7f6; --panel:#ffffff; }
    * { box-sizing:border-box; }
    html, body { height:100%; margin:0; background:var(--bg); color:var(--ink); }
    body { font-family:Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; overflow:hidden; }
    #viewer { width:100vw; height:100vh; display:block; }
    .bar { position:fixed; top:0; left:0; right:0; z-index:3; display:flex; gap:12px; align-items:center; justify-content:space-between;
      padding:10px 14px; background:rgba(255,255,255,.9); border-bottom:1px solid var(--line); backdrop-filter:blur(14px); }
    .title { font-size:15px; font-weight:760; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .tools { display:flex; gap:8px; align-items:center; flex-wrap:wrap; justify-content:flex-end; }
    button, label, select { border:1px solid var(--line); background:white; border-radius:6px; padding:7px 10px; font:inherit; font-size:13px; }
    button, label { cursor:pointer; color:var(--accent); font-weight:740; }
    input[type=file] { display:none; }
    .hint { color:var(--muted); font-size:12px; }
  </style>
</head>
<body>
  <div class="bar">
    <div class="title">__TITLE__</div>
    <div class="tools">
      <button id="play">Pause</button>
      <select id="speed" title="Playback speed">
        <option value="0.5">0.5x</option>
        <option value="1" selected>1x</option>
        <option value="1.5">1.5x</option>
        <option value="2">2x</option>
      </select>
      <label>Upload GLB<input id="glbUpload" type="file" accept=".glb,model/gltf-binary"></label>
      <span class="hint" id="status">Loading model...</span>
    </div>
  </div>
  <canvas id="viewer"></canvas>
  <script id="payload" type="application/json">__PAYLOAD__</script>
  <script type="importmap">
    {"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.161.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.161.0/examples/jsm/"}}
  </script>
  <script type="module">
    import * as THREE from 'three';
    import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
    import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

    const data = JSON.parse(document.getElementById('payload').textContent);
    const canvas = document.getElementById('viewer');
    const renderer = new THREE.WebGLRenderer({ canvas, antialias:true, alpha:false });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(innerWidth, innerHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf5f7f6);
    const camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 0.01, 1000);
    camera.position.set(2.2, 1.5, 3.0);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(0, 0.8, 0);

    scene.add(new THREE.HemisphereLight(0xffffff, 0xb7c0bd, 2.4));
    const key = new THREE.DirectionalLight(0xffffff, 2.6);
    key.position.set(3, 5, 4);
    scene.add(key);
    const grid = new THREE.GridHelper(16, 80, 0xb8c7c2, 0xe1e8e5);
    scene.add(grid);

    const loader = new GLTFLoader();
    const clock = new THREE.Clock();
    let root = null, mixer = null, duration = 0, playing = true;
    const status = document.getElementById('status');
    const speed = document.getElementById('speed');

    function disposeObject(obj) {
      obj.traverse((child) => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) {
          if (Array.isArray(child.material)) child.material.forEach((m) => m.dispose?.());
          else child.material.dispose?.();
        }
      });
    }
    function frameObject(obj) {
      const box = new THREE.Box3().setFromObject(obj);
      if (!Number.isFinite(box.min.x) || box.isEmpty()) return;
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const radius = Math.max(size.x, size.y, size.z, 1e-3);
      controls.target.copy(center);
      camera.position.set(center.x + radius * 1.5, center.y + radius * 0.8, center.z + radius * 2.0);
      camera.near = Math.max(radius / 1000, 0.001);
      camera.far = Math.max(radius * 20, 10);
      camera.updateProjectionMatrix();
    }
    function loadGlb(url) {
      status.textContent = 'Loading model...';
      loader.load(url, (gltf) => {
        if (root) { scene.remove(root); disposeObject(root); }
        root = gltf.scene;
        root.traverse((child) => {
          if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;
            if (child.material) child.material.side = THREE.DoubleSide;
          }
        });
        scene.add(root);
        mixer = gltf.animations.length ? new THREE.AnimationMixer(root) : null;
        if (mixer) {
          const action = mixer.clipAction(gltf.animations[0]);
          action.play();
          duration = gltf.animations[0].duration || 0;
        }
        frameObject(root);
        status.textContent = mixer ? `Animation: ${duration.toFixed(2)} s` : 'Model loaded';
      }, undefined, (error) => {
        console.error(error);
        status.textContent = 'Could not load model. Use Upload GLB.';
      });
    }
    if (data.glb_path) loadGlb(data.glb_path);

    document.getElementById('glbUpload').addEventListener('change', (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      loadGlb(URL.createObjectURL(file));
    });
    document.getElementById('play').addEventListener('click', (event) => {
      playing = !playing;
      event.currentTarget.textContent = playing ? 'Pause' : 'Play';
    });
    addEventListener('resize', () => {
      camera.aspect = innerWidth / innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(innerWidth, innerHeight);
    });
    function animate() {
      requestAnimationFrame(animate);
      const dt = clock.getDelta() * Number(speed.value || 1);
      if (playing && mixer) mixer.update(dt);
      controls.update();
      renderer.render(scene, camera);
    }
    animate();
  </script>
</body>
</html>
"""
    html = html.replace("__TITLE__", safe_title).replace("__PAYLOAD__", payload_json)
    html_path.write_text(html, encoding="utf-8", newline="\n")
    return html_path


def _storage_for_visualizer(
    path: str | Path | None,
    *,
    max_columns: int | None = None,
) -> dict[str, Any] | None:
    if path is None:
        return None
    from .io.storage import read_storage

    storage_path = Path(path).expanduser().resolve()
    if not storage_path.is_file():
        raise FileNotFoundError(f"Storage file not found: {storage_path}")
    df = read_storage(storage_path)
    if df.empty:
        return {"path": storage_path.name, "columns": [], "time": [], "series": {}}
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
    selected = numeric_cols if max_columns is None else numeric_cols[:max_columns]
    return {
        "path": storage_path.name,
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
    norm = {name: re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_") for name in marker_names}
    index = {name: i for i, name in enumerate(marker_names)}

    def side_of(name: str) -> str | None:
        tokens = {token for token in re.split(r"[_\W]+", norm[name]) if token}
        compact = norm[name].replace("_", "")
        if "right" in tokens or "r" in tokens or compact.startswith("right"):
            return "right"
        if "left" in tokens or "l" in tokens or compact.startswith("left"):
            return "left"
        return None

    def has_part(name: str, part: str) -> bool:
        compact = norm[name].replace("_", "")
        aliases = {
            "foot": ("foot", "toe", "footindex", "bofoot", "calcn"),
            "heel": ("heel", "calc"),
            "pelvis": ("pelvis", "hip"),
            "torso": ("torso", "spine", "sternum", "chest", "shoulder"),
        }
        return any(alias in compact for alias in aliases.get(part, (part,)))

    def find(part: str, side: str | None = None, *, prefer: tuple[str, ...] = ()) -> int | None:
        matches = [
            name
            for name in marker_names
            if has_part(name, part) and (side is None or side_of(name) == side)
        ]
        if not matches:
            return None
        if prefer:
            matches.sort(
                key=lambda name: (
                    0
                    if any(token in norm[name].replace("_", "") for token in prefer)
                    else 1,
                    len(norm[name]),
                )
            )
        else:
            matches.sort(key=lambda name: len(norm[name]))
        return index[matches[0]]

    left_hip = find("hip", "left")
    right_hip = find("hip", "right")
    pelvis = None
    if left_hip is not None and right_hip is not None:
        pelvis = left_hip
    torso = find("torso")

    pairs = [
        (pelvis, torso),
        (right_hip, find("knee", "right")),
        (find("knee", "right"), find("ankle", "right")),
        (find("ankle", "right"), find("foot", "right", prefer=("footindex", "toe"))),
        (find("ankle", "right"), find("heel", "right")),
        (left_hip, find("knee", "left")),
        (find("knee", "left"), find("ankle", "left")),
        (find("ankle", "left"), find("foot", "left", prefer=("footindex", "toe"))),
        (find("ankle", "left"), find("heel", "left")),
        (find("shoulder", "right"), find("elbow", "right")),
        (find("elbow", "right"), find("wrist", "right")),
        (find("shoulder", "left"), find("elbow", "left")),
        (find("elbow", "left"), find("wrist", "left")),
        (find("shoulder", "right"), find("shoulder", "left")),
        (right_hip, left_hip),
        (find("shoulder", "right"), right_hip),
        (find("shoulder", "left"), left_hip),
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


def _auto_visualizer_stride(
    storage_path: str | Path | None,
    *,
    max_frames: int,
    requested_stride: int,
) -> int:
    requested_stride = max(1, int(requested_stride))
    max_frames = max(1, int(max_frames))
    if storage_path is None:
        return requested_stride
    try:
        from .io.storage import read_storage

        df = read_storage(Path(storage_path).expanduser().resolve())
        frame_count = len(df)
    except Exception:
        return requested_stride
    if frame_count <= 0:
        return requested_stride
    return max(requested_stride, int(math.ceil(frame_count / max_frames)))


def _body_transform_payload(
    *,
    osim_path: str | Path | None,
    ik_path: str | Path | None,
    target_time: list[float],
) -> dict[str, Any] | None:
    if osim_path is None or ik_path is None or not target_time:
        return None
    try:
        osim = _require_opensim_dependency()
        model = osim.Model(str(Path(osim_path).expanduser().resolve()))
        state = model.initSystem()
        in_degrees, ik_times, labels, ik_data = _read_mot_or_sto(Path(ik_path).expanduser().resolve(), osim)
        mapping, _ = _coordinate_mapping(model, labels, in_degrees=in_degrees)
        body_set = model.getBodySet()
        body_names = [body_set.get(i).getName() for i in range(body_set.getSize())]
    except Exception as exc:
        return {"names": [], "time": [], "frames": [], "segments": [], "warning": str(exc)}

    if not mapping or len(ik_times) < 2:
        return {
            "names": body_names,
            "time": [],
            "frames": [],
            "segments": [],
            "warning": "Could not map IK coordinates to OpenSim body transforms.",
        }

    frames = []
    for target in np.asarray(target_time, dtype=float):
        if not np.isfinite(target):
            continue
        row = np.empty(ik_data.shape[1], dtype=float)
        for col in range(ik_data.shape[1]):
            row[col] = float(np.interp(target, ik_times, ik_data[:, col]))
        for coord, col, convert_degrees in mapping:
            value = float(row[col])
            if convert_degrees:
                value *= np.pi / 180.0
            try:
                coord.setValue(state, value, True)
            except Exception:
                coord.setValue(state, value)
        model.realizePosition(state)
        frame = []
        for body_name in body_names:
            transform = body_set.get(body_name).getTransformInGround(state)
            frame.append(
                {
                    "p": np.round(_simtk_vec3_to_np(transform.p()), 6).astype(float).tolist(),
                    "q": np.round(_matrix_to_quat_xyzw(_simtk_rot_to_np(transform.R())), 6)
                    .astype(float)
                    .tolist(),
                }
            )
        frames.append(frame)

    return {
        "names": body_names,
        "time": [float(t) for t in target_time],
        "frames": frames,
        "segments": _infer_body_segments(body_names),
    }


def _infer_body_segments(body_names: list[str]) -> list[list[int]]:
    index = {name: i for i, name in enumerate(body_names)}

    def has(name: str) -> bool:
        return name in index

    pairs = []

    def add(a: str, b: str) -> None:
        if has(a) and has(b):
            pairs.append([index[a], index[b]])

    add("pelvis", "torso")
    add("torso", "head")
    add("pelvis", "femur_r")
    add("femur_r", "tibia_r")
    add("tibia_r", "talus_r")
    add("talus_r", "calcn_r")
    add("calcn_r", "toes_r")
    add("pelvis", "femur_l")
    add("femur_l", "tibia_l")
    add("tibia_l", "talus_l")
    add("talus_l", "calcn_l")
    add("calcn_l", "toes_l")
    add("torso", "humerus_r")
    add("humerus_r", "ulna_r")
    add("ulna_r", "radius_r")
    add("radius_r", "hand_r")
    add("torso", "humerus_l")
    add("humerus_l", "ulna_l")
    add("ulna_l", "radius_l")
    add("radius_l", "hand_l")

    # Fallback for common simplified/full-body variants.
    for side in ("r", "l"):
        add("pelvis", f"femur_{side}")
        add(f"femur_{side}", f"tibia_{side}")
        add(f"tibia_{side}", f"foot_{side}")
        add("torso", f"humerus_{side}")
        add(f"humerus_{side}", f"radius_{side}")
        add(f"radius_{side}", f"hand_{side}")

    out = []
    seen = set()
    for a, b in pairs:
        key = tuple(sorted((a, b)))
        if a != b and key not in seen:
            out.append([a, b])
            seen.add(key)
    return out


def _external_load_payload(
    path: str | Path | None,
    *,
    target_time: list[float],
    osim_path: str | Path | None = None,
    ik_path: str | Path | None = None,
) -> dict[str, Any] | None:
    if path is None:
        return None
    from .io.storage import read_storage

    force_path = Path(path).expanduser().resolve()
    if not force_path.is_file():
        raise FileNotFoundError(f"External-load MOT file not found: {force_path}")
    df = read_storage(force_path)
    if df.empty or "time" not in df.columns:
        return None
    df = df.copy()
    df["time"] = pd.to_numeric(df["time"], errors="coerce")
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["time"])
    df = df.sort_values("time").drop_duplicates(subset=["time"], keep="last").reset_index(drop=True)
    src_t = df["time"].to_numpy(dtype=float)
    load_names = sorted(
        {
            col[:-3]
            for col in df.columns
            if col.endswith("_vx") and f"{col[:-3]}_px" in df.columns
        }
    )
    load_metadata = _external_loads_xml_metadata(force_path)
    transform_payload, transform_warning = _external_load_frame_transforms(
        load_metadata,
        target_time=target_time,
        osim_path=osim_path,
        ik_path=ik_path,
    )
    if len(src_t) < 2 or not load_names:
        return {
            "path": str(force_path),
            "names": load_names,
            "frames": [],
            "diagnostics": {
                "warning": "No usable external-force samples were found.",
                "load_metadata": load_metadata,
            },
        }
    target = np.asarray(target_time, dtype=float)
    target = target[np.isfinite(target)]
    if len(target) == 0:
        return {"path": str(force_path), "names": load_names, "frames": []}

    target_start = float(target[0])
    target_end = float(target[-1])
    source_start = float(src_t[0])
    source_end = float(src_t[-1])
    overlap = max(0.0, min(target_end, source_end) - max(target_start, source_start))
    target_duration = max(1e-12, target_end - target_start)
    overlap_fraction = overlap / target_duration
    frames = []
    active_counts = {name: 0 for name in load_names}
    max_magnitudes = {name: 0.0 for name in load_names}

    for i, t in enumerate(np.asarray(target_time, dtype=float)):
        frame = []
        for name in load_names:
            values = {}
            for suffix in ("vx", "vy", "vz", "px", "py", "pz"):
                col = f"{name}_{suffix}"
                y = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
                arr = y.fillna(0.0).to_numpy(dtype=float)
                values[suffix] = float(np.interp(t, src_t, arr, left=0.0, right=0.0))
            point = np.asarray([values["px"], values["py"], values["pz"]], dtype=float)
            force = np.asarray([values["vx"], values["vy"], values["vz"]], dtype=float)
            meta = load_metadata.get(name, {})
            point_frame = str(meta.get("point_expressed_in") or "/ground")
            force_frame = str(meta.get("force_expressed_in") or "/ground")
            point_transform = transform_payload.get((i, _frame_key(point_frame)))
            force_transform = transform_payload.get((i, _frame_key(force_frame)))
            raw_point = point.copy()
            if point_transform is not None:
                point = point_transform["R"] @ point + point_transform["p"]
            if force_transform is not None:
                force = force_transform["R"] @ force
            magnitude = float(np.linalg.norm(force))
            if magnitude > 1e-6:
                active_counts[name] += 1
                max_magnitudes[name] = max(max_magnitudes[name], magnitude)
            frame.append(
                {
                    "name": name,
                    "point": np.round(point, 6).astype(float).tolist(),
                    "force": np.round(force, 6).astype(float).tolist(),
                    "magnitude": magnitude,
                    "applied_to_body": meta.get("applied_to_body"),
                    "point_expressed_in": point_frame,
                    "force_expressed_in": force_frame,
                    "raw_point": np.round(raw_point, 6).astype(float).tolist(),
                }
            )
        frames.append(frame)

    total_active = sum(active_counts.values())
    warning = None
    if overlap_fraction < 0.75:
        warning = (
            "External-load time range does not fully overlap the displayed IK frames. "
            "Regenerate external loads against the IK time vector before interpreting force arrows."
        )
    elif total_active == 0:
        warning = "External-load file was read, but all displayed force vectors are zero."
    elif transform_warning:
        warning = transform_warning

    return {
        "path": str(force_path),
        "names": load_names,
        "frames": frames,
        "diagnostics": {
            "source_time_range": [source_start, source_end],
            "target_time_range": [target_start, target_end],
            "overlap_fraction": float(overlap_fraction),
            "active_frame_counts": active_counts,
            "max_magnitudes": max_magnitudes,
            "load_metadata": load_metadata,
            "frame_transform_warning": transform_warning,
            "warning": warning,
        },
    }


def _external_loads_xml_metadata(mot_path: Path) -> dict[str, dict[str, str]]:
    xml_path = mot_path.with_name(mot_path.name.replace("_external_loads.mot", "_ExternalLoads.xml"))
    if xml_path == mot_path or not xml_path.is_file():
        candidates = sorted(mot_path.parent.glob("*ExternalLoads*.xml"))
        xml_path = candidates[0] if candidates else xml_path
    if not xml_path.is_file():
        return {}
    try:
        root = ET.parse(xml_path).getroot()
    except Exception:
        return {}

    out: dict[str, dict[str, str]] = {}
    for elem in root.iter():
        if _tag(elem) != "externalforce":
            continue
        name = elem.attrib.get("name")
        if not name:
            continue
        meta = {}
        for child in list(elem):
            tag = _tag(child)
            text = (child.text or "").strip()
            if tag == "applied_to_body":
                meta["applied_to_body"] = text
            elif tag == "force_expressed_in_body":
                meta["force_expressed_in"] = text
            elif tag == "point_expressed_in_body":
                meta["point_expressed_in"] = text
        out[name] = meta
    return out


def _frame_key(frame: str | None) -> str:
    if frame is None:
        return "ground"
    key = str(frame).strip().strip("/")
    if not key or key.lower() == "ground":
        return "ground"
    return key.split("/")[-1]


def _external_load_frame_transforms(
    load_metadata: dict[str, dict[str, str]],
    *,
    target_time: list[float],
    osim_path: str | Path | None,
    ik_path: str | Path | None,
) -> tuple[dict[tuple[int, str], dict[str, np.ndarray]], str | None]:
    needed_frames = {
        _frame_key(meta.get(field))
        for meta in load_metadata.values()
        for field in ("point_expressed_in", "force_expressed_in")
        if _frame_key(meta.get(field)) != "ground"
    }
    if not needed_frames:
        return {}, None
    if osim_path is None or ik_path is None:
        return {}, (
            "External-load points are body-local, but the model and IK motion were not available "
            "to convert them for display."
        )
    try:
        osim = _require_opensim_dependency()
        model = osim.Model(str(Path(osim_path).expanduser().resolve()))
        state = model.initSystem()
        in_degrees, ik_times, labels, ik_data = _read_mot_or_sto(Path(ik_path).expanduser().resolve(), osim)
        mapping, _ = _coordinate_mapping(model, labels, in_degrees=in_degrees)
        frames = _resolve_opensim_frames(model, needed_frames)
    except Exception as exc:
        return {}, f"External-load display could not resolve body-local force points: {exc}"

    if not mapping or len(ik_times) < 2:
        return {}, "External-load display could not map IK coordinates for body-local force points."

    transforms: dict[tuple[int, str], dict[str, np.ndarray]] = {}
    targets = np.asarray(target_time, dtype=float)
    for idx, target in enumerate(targets):
        if not np.isfinite(target):
            continue
        row = np.empty(ik_data.shape[1], dtype=float)
        for col in range(ik_data.shape[1]):
            series = ik_data[:, col]
            row[col] = float(np.interp(target, ik_times, series))
        for coord, col, convert_degrees in mapping:
            value = float(row[col])
            if convert_degrees:
                value *= np.pi / 180.0
            try:
                coord.setValue(state, value, True)
            except Exception:
                coord.setValue(state, value)
        model.realizePosition(state)
        for key, frame in frames.items():
            transform = frame.getTransformInGround(state)
            transforms[(idx, key)] = {
                "R": _simtk_rot_to_np(transform.R()),
                "p": _simtk_vec3_to_np(transform.p()),
            }
    return transforms, None


def _resolve_opensim_frames(model, frame_names: set[str]) -> dict[str, Any]:
    body_set = model.getBodySet()
    body_map = {body_set.get(i).getName(): body_set.get(i) for i in range(body_set.getSize())}
    out = {}
    missing = []
    for name in frame_names:
        if name in body_map:
            out[name] = body_map[name]
        else:
            missing.append(name)
    if missing:
        sample = ", ".join(sorted(body_map)[:12])
        raise ValueError(f"unknown OpenSim body/frame(s) {missing}; available examples: {sample}")
    return out


def _write_visualizer_html(
    html_path: Path,
    *,
    title: str,
    payload: dict[str, Any],
) -> Path:
    html_path.parent.mkdir(parents=True, exist_ok=True)
    payload_json = json.dumps(_json_safe(payload), allow_nan=False)
    safe_title = escape(title)
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <style>
    :root { --ink:#17211e; --muted:#66736f; --line:#d9e2df; --panel:#ffffff; --bg:#f5f7f6; --accent:#0f766e; --force:#d65a31; --soft:#eef4f1; }
    * { box-sizing:border-box; }
    body { margin:0; font-family:Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; background:var(--bg); color:var(--ink); }
    header { padding:16px 20px; border-bottom:1px solid var(--line); background:rgba(255,255,255,.93); position:sticky; top:0; z-index:5; backdrop-filter:blur(14px); }
    h1 { margin:0; font-size:22px; letter-spacing:0; }
    .sub { color:var(--muted); margin-top:4px; font-size:13px; line-height:1.4; }
    main { display:grid; grid-template-columns:minmax(470px, 1.28fr) minmax(360px, .72fr); gap:14px; padding:14px; align-items:start; }
    section { background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; box-shadow:0 8px 22px rgba(37,53,48,.05); }
    .panel-title { min-height:42px; padding:10px 12px; border-bottom:1px solid var(--line); font-weight:760; font-size:13px; display:flex; justify-content:space-between; gap:10px; align-items:center; }
    .visual-wrap { position:relative; height:650px; background:#eef3f1; }
    #threeScene { width:100%; height:100%; display:block; }
    .viewer-tools { display:flex; align-items:center; gap:8px; padding:10px 12px; border-top:1px solid var(--line); background:#fbfcfc; flex-wrap:wrap; }
    button, select, label { border:1px solid var(--line); background:white; border-radius:6px; padding:7px 10px; font:inherit; font-size:13px; }
    button, label { cursor:pointer; font-weight:740; color:var(--accent); }
    button.active { background:var(--accent); color:#fff; border-color:var(--accent); }
    input[type=range] { flex:1; min-width:160px; accent-color:var(--accent); }
    input[type=file] { display:none; }
    .legend { position:absolute; left:12px; bottom:12px; display:flex; gap:8px; flex-wrap:wrap; z-index:2; }
    .pill { background:rgba(255,255,255,.88); border:1px solid var(--line); border-radius:999px; padding:5px 9px; font-size:12px; color:var(--muted); }
    .stack { display:grid; gap:14px; }
    .plotbox { padding:10px 10px 12px; }
    canvas.plot { width:100%; height:230px; display:block; border:1px solid var(--line); border-radius:8px; background:white; }
    .stats { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; padding:10px; }
    .stat { border:1px solid var(--line); border-radius:8px; padding:9px; background:#fbfcfc; min-width:0; }
    .stat b { display:block; font-size:18px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .stat span { color:var(--muted); font-size:12px; }
    .notice { padding:10px 12px; color:var(--muted); font-size:12px; border-top:1px solid var(--line); background:#fbfcfc; }
    @media (max-width: 980px) { main { grid-template-columns:1fr; } .visual-wrap { height:540px; } }
    @media (max-width: 620px) { main { padding:8px; } .stats { grid-template-columns:repeat(2,1fr); } h1 { font-size:18px; } }
  </style>
</head>
<body>
  <header>
    <h1>__TITLE__</h1>
    <div class="sub">Fast OpenSim body playback, optional GLB mesh playback, external-force arrows, complete IK coordinate plots, and complete inverse-dynamics traces.</div>
  </header>
  <main>
    <section>
      <div class="panel-title">
        <span>3D Model, Markers, And Forces</span>
        <span id="viewerStatus" class="sub">Ready</span>
      </div>
      <div class="visual-wrap">
        <canvas id="threeScene"></canvas>
        <div class="legend">
          <span class="pill">teal: markers</span>
          <span class="pill">gray: body proxies</span>
          <span class="pill">dark lines: marker skeleton</span>
          <span class="pill">orange: external forces</span>
        </div>
      </div>
      <div class="viewer-tools">
        <button id="play">Play</button>
        <input id="scrub" type="range" min="0" max="0" value="0">
        <span id="time">0.000 s</span>
        <select id="speed" title="Playback speed">
          <option value="0.5">0.5x</option>
          <option value="1" selected>1x</option>
          <option value="1.5">1.5x</option>
          <option value="2">2x</option>
        </select>
        <button id="toggleModel" class="active">Model</button>
        <button id="toggleMarkers" class="active">Markers</button>
        <button id="toggleForces" class="active">Forces</button>
        <label>Upload GLB<input id="glbUpload" type="file" accept=".glb,model/gltf-binary"></label>
      </div>
      <div class="notice" id="viewerNotice">Inspect synchronized OpenSim body motion, markers, external forces, IK, and inverse dynamics. Upload a GLB when full anatomical surface meshes are needed.</div>
    </section>
    <div class="stack">
      <section>
        <div class="panel-title">Run Summary</div>
        <div class="stats" id="stats"></div>
      </section>
      <section>
        <div class="panel-title">IK Coordinates <select id="ikSelect"></select></div>
        <div class="plotbox"><canvas id="ikPlot" class="plot"></canvas></div>
      </section>
      <section>
        <div class="panel-title">Inverse Dynamics <select id="idSelect"></select></div>
        <div class="plotbox"><canvas id="idPlot" class="plot"></canvas></div>
      </section>
    </div>
  </main>
  <script id="payload" type="application/json">__PAYLOAD__</script>
  <script type="importmap">
    {"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.161.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.161.0/examples/jsm/"}}
  </script>
  <script type="module">
    import * as THREE from 'three';
    import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
    import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

    const emptyMarkers = () => ({names:[], time:[], frames:[], segments:[]});
    const emptyBodies = () => ({names:[], time:[], frames:[], segments:[]});
    const emptyStore = () => ({path:null, columns:[], time:[], series:{}});
    let data = JSON.parse(document.getElementById('payload').textContent);
    let marker = data.markers || emptyMarkers();
    let body = data.bodies || emptyBodies();
    let force = data.forces || {names:[], frames:[]};
    const scrub = document.getElementById('scrub');
    const timeLabel = document.getElementById('time');
    const playBtn = document.getElementById('play');
    const speedSelect = document.getElementById('speed');
    const status = document.getElementById('viewerStatus');
    const notice = document.getElementById('viewerNotice');
    let idx = 0, playing = false, lastTick = 0;
    let timelineFrames = Math.max(1, marker.frames.length);
    scrub.max = Math.max(0, marker.frames.length - 1);
    if (force?.diagnostics?.warning) {
      notice.textContent = force.diagnostics.warning;
    }

    function refreshStats() {
      document.getElementById('stats').innerHTML = [
        ['Frames', marker.frames.length],
        ['Bodies', body.names?.length || 0],
        ['Markers', marker.names.length],
        ['Forces', (force.names || []).length],
        ['IK traces', data.ik?.columns?.length || 0],
        ['ID traces', data.id?.columns?.length || 0],
        ['Duration', marker.time.length ? (marker.time[marker.time.length-1]-marker.time[0]).toFixed(3)+' s' : '0 s']
      ].map(([k,v]) => `<div class="stat"><b>${v}</b><span>${k}</span></div>`).join('');
    }
    refreshStats();

    const canvas = document.getElementById('threeScene');
    const renderer = new THREE.WebGLRenderer({ canvas, antialias:true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf0f4f2);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 1000);
    camera.position.set(2.4, 1.5, 3.0);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(0, .8, 0);
    scene.add(new THREE.HemisphereLight(0xffffff, 0xb7c0bd, 2.5));
    const key = new THREE.DirectionalLight(0xffffff, 2.6);
    key.position.set(3, 5, 4);
    scene.add(key);
    scene.add(new THREE.GridHelper(16, 80, 0xb7c7c2, 0xdfe9e5));

    const markersGroup = new THREE.Group();
    const skeletonGroup = new THREE.Group();
    const forceGroup = new THREE.Group();
    const modelGroup = new THREE.Group();
    const bodyProxyGroup = new THREE.Group();
    modelGroup.add(bodyProxyGroup);
    scene.add(modelGroup, skeletonGroup, markersGroup, forceGroup);

    const bodyMaterial = new THREE.MeshStandardMaterial({ color:0x6b7470, roughness:.68, metalness:0.0 });
    const bodyJointMaterial = new THREE.MeshStandardMaterial({ color:0x39433f, roughness:.62, metalness:0.0 });
    const bodyJointGeom = new THREE.SphereGeometry(0.026, 16, 12);
    const bodyLineMaterial = new THREE.LineBasicMaterial({ color:0x56615d, linewidth:2 });
    let bodyMeshes = [];
    let bodyLines = [];
    function bodyScale(name) {
      const n = String(name || '').toLowerCase();
      if (n.includes('pelvis') || n.includes('torso')) return [0.09, 0.055, 0.055];
      if (n.includes('head')) return [0.075, 0.075, 0.075];
      if (n.includes('femur') || n.includes('tibia') || n.includes('humerus')) return [0.065, 0.035, 0.035];
      if (n.includes('foot') || n.includes('calcn')) return [0.075, 0.035, 0.045];
      return [0.045, 0.032, 0.032];
    }
    function rebuildBodyScene() {
      bodyProxyGroup.clear();
      bodyMeshes = (body.names || []).map((name) => {
        const mesh = new THREE.Mesh(bodyJointGeom, bodyMaterial);
        const s = bodyScale(name);
        mesh.scale.set(s[0] / 0.026, s[1] / 0.026, s[2] / 0.026);
        mesh.name = name;
        bodyProxyGroup.add(mesh);
        return mesh;
      });
      bodyLines = (body.segments || []).map(([a,b]) => {
        const geom = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
        const line = new THREE.Line(geom, bodyLineMaterial);
        line.userData = { a, b };
        bodyProxyGroup.add(line);
        return line;
      });
      if (bodyMeshes.length) status.textContent = 'Fast body viewer ready';
    }
    rebuildBodyScene();

    const markerMaterial = new THREE.MeshStandardMaterial({ color:0x0f766e, roughness:.55, metalness:0.0 });
    const markerGeom = new THREE.SphereGeometry(0.018, 16, 12);
    let markerMeshes = [];
    const skeletonMaterial = new THREE.LineBasicMaterial({ color:0x24302d, linewidth:2 });
    let skeletonLines = [];
    function rebuildMarkerScene() {
      markersGroup.clear();
      skeletonGroup.clear();
      markerMeshes = (marker.names || []).map((name) => {
        const mesh = new THREE.Mesh(markerGeom, markerMaterial);
        mesh.name = name;
        markersGroup.add(mesh);
        return mesh;
      });
      skeletonLines = (marker.segments || []).map(([a,b]) => {
        const geom = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
        const line = new THREE.Line(geom, skeletonMaterial);
        line.userData = { a, b };
        skeletonGroup.add(line);
        return line;
      });
    }
    rebuildMarkerScene();
    function validPoint(p) {
      return p && p.length === 3 && p.every(Number.isFinite);
    }
    function setLinePositions(line, pa, pb) {
      const pos = line.geometry.attributes.position;
      pos.setXYZ(0, pa[0], pa[1], pa[2]);
      pos.setXYZ(1, pb[0], pb[1], pb[2]);
      pos.needsUpdate = true;
      line.geometry.computeBoundingSphere();
    }
    function updateForces(i) {
      forceGroup.clear();
      const loads = (force.frames || [])[i] || [];
      let maxMag = 0;
      for (const load of loads) maxMag = Math.max(maxMag, Math.hypot(...load.force));
      const scale = maxMag > 0 ? (data.force_scale || 0.35) / maxMag : 1;
      for (const load of loads) {
        const p = load.point, v = load.force;
        if (!validPoint(p) || !validPoint(v)) continue;
        const mag = Math.hypot(...v);
        if (!Number.isFinite(mag) || mag <= 1e-9) continue;
        const dir = new THREE.Vector3(v[0], v[1], v[2]).normalize();
        const origin = new THREE.Vector3(p[0], p[1], p[2]);
        const arrow = new THREE.ArrowHelper(dir, origin, Math.max(0.05, mag * scale), 0xd65a31, 0.075, 0.035);
        forceGroup.add(arrow);
      }
    }
    function updateBodies(i) {
      const frame = (body.frames || [])[i] || [];
      bodyMeshes.forEach((mesh, bi) => {
        const item = frame[bi];
        const p = item?.p;
        mesh.visible = validPoint(p);
        if (mesh.visible) {
          mesh.position.set(p[0], p[1], p[2]);
          const q = item?.q;
          if (q && q.length === 4 && q.every(Number.isFinite)) {
            mesh.quaternion.set(q[0], q[1], q[2], q[3]);
          }
        }
      });
      bodyLines.forEach((line) => {
        const a = frame[line.userData.a]?.p, b = frame[line.userData.b]?.p;
        line.visible = validPoint(a) && validPoint(b);
        if (line.visible) setLinePositions(line, a, b);
      });
    }
    function updateFrame(i) {
      const n = Math.max(1, timelineFrames);
      idx = ((Math.round(i) % n) + n) % n;
      const frame = marker.frames[idx] || [];
      markerMeshes.forEach((mesh, mi) => {
        const p = frame[mi];
        mesh.visible = validPoint(p);
        if (mesh.visible) mesh.position.set(p[0], p[1], p[2]);
      });
      skeletonLines.forEach((line) => {
        const a = frame[line.userData.a], b = frame[line.userData.b];
        line.visible = validPoint(a) && validPoint(b);
        if (line.visible) setLinePositions(line, a, b);
      });
      updateBodies(idx);
      updateForces(idx);
      scrub.value = idx;
      setMixerToFrame(idx);
      const shownTime = marker.time.length
        ? (marker.time[idx] || 0)
        : (glbDuration && timelineFrames > 1 ? (idx / (timelineFrames - 1)) * glbDuration : 0);
      timeLabel.textContent = shownTime.toFixed(3) + ' s';
    }
    function resizeRenderer() {
      const rect = canvas.parentElement.getBoundingClientRect();
      renderer.setSize(rect.width, rect.height, false);
      camera.aspect = rect.width / rect.height;
      camera.updateProjectionMatrix();
    }
    function frameScene() {
      const box = new THREE.Box3();
      let hasBox = false;
      for (const group of [modelGroup, markersGroup, skeletonGroup]) {
        const b = new THREE.Box3().setFromObject(group);
        if (Number.isFinite(b.min.x) && !b.isEmpty()) {
          if (!hasBox) box.copy(b); else box.union(b);
          hasBox = true;
        }
      }
      if (!hasBox) return;
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const radius = Math.max(size.x, size.y, size.z, 0.5);
      controls.target.copy(center);
      camera.position.set(center.x + radius * 1.35, center.y + radius * 0.75, center.z + radius * 2.0);
      camera.near = Math.max(radius / 1000, 0.001);
      camera.far = Math.max(radius * 30, 10);
      camera.updateProjectionMatrix();
    }

    const loader = new GLTFLoader();
    let mixer = null, glbDuration = 0, glbRoot = null;
    function syncTimeline() {
      timelineFrames = marker.frames.length || (glbDuration > 0 ? 300 : 1);
      scrub.max = Math.max(0, timelineFrames - 1);
      if (idx >= timelineFrames) idx = 0;
    }
    function disposeObject(obj) {
      obj.traverse((child) => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) {
          if (Array.isArray(child.material)) child.material.forEach((m) => m.dispose?.());
          else child.material.dispose?.();
        }
      });
    }
    function loadGlb(url) {
      status.textContent = 'Loading GLB...';
      loader.load(url, (gltf) => {
        const embedded = gltf.parser?.json?.extras?.monomech?.visualizer;
        if (embedded) applyEmbeddedPayload(embedded);
        if (glbRoot) { modelGroup.remove(glbRoot); disposeObject(glbRoot); }
        glbRoot = gltf.scene;
        glbRoot.traverse((child) => {
          if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;
            if (child.material) child.material.side = THREE.DoubleSide;
          }
        });
        modelGroup.add(glbRoot);
        bodyProxyGroup.visible = false;
        mixer = gltf.animations.length ? new THREE.AnimationMixer(glbRoot) : null;
        glbDuration = gltf.animations[0]?.duration || 0;
        if (mixer) mixer.clipAction(gltf.animations[0]).play();
        syncTimeline();
        modelGroup.visible = true;
        document.getElementById('toggleModel').classList.add('active');
        frameScene();
        updateFrame(idx);
        status.textContent = mixer ? `GLB loaded (${glbDuration.toFixed(2)} s)` : 'GLB loaded';
      }, undefined, (error) => {
        console.error(error);
        status.textContent = 'GLB unavailable. Upload one or use markers.';
      });
    }
    function setMixerToFrame(i) {
      if (!mixer || !glbDuration) return;
      let frac = 0;
      if (marker.time.length >= 2) {
        const t0 = marker.time[0], t1 = marker.time[marker.time.length - 1];
        frac = t1 > t0 ? (marker.time[i] - t0) / (t1 - t0) : 0;
      } else {
        frac = timelineFrames > 1 ? i / (timelineFrames - 1) : 0;
      }
      mixer.setTime(Math.max(0, Math.min(glbDuration, frac * glbDuration)));
      modelGroup.updateMatrixWorld(true);
    }
    if (data.glb_path) loadGlb(data.glb_path);
    else status.textContent = 'Upload a GLB or use the marker view.';
    document.getElementById('glbUpload').addEventListener('change', (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      loadGlb(URL.createObjectURL(file));
    });

    scrub.addEventListener('input', e => updateFrame(Number(e.target.value)));
    playBtn.addEventListener('click', () => {
      playing = !playing;
      playBtn.textContent = playing ? 'Pause' : 'Play';
    });
    function toggleButton(id, ...groups) {
      const btn = document.getElementById(id);
      btn.addEventListener('click', () => {
        const visible = !groups[0].visible;
        for (const group of groups) group.visible = visible;
        btn.classList.toggle('active', visible);
      });
    }
    toggleButton('toggleModel', modelGroup);
    toggleButton('toggleMarkers', markersGroup);
    toggleButton('toggleForces', forceGroup);

    function makeSeriesPlot(canvasId, store, selectId, color) {
      const canvas = document.getElementById(canvasId);
      const ctx = canvas.getContext('2d');
      const select = document.getElementById(selectId);
      const palette = ['#0f766e', '#d65a31', '#2f6fed', '#7a4f9a', '#8a6f00', '#256c4f', '#b42318', '#475467'];
      function refreshSelect() {
        const cols = store?.columns || [];
        select.innerHTML = cols.length
          ? `<option value="__all__">All signals (${cols.length})</option>` + cols.map(c => `<option value="${c}">${c}</option>`).join('')
          : '<option>No data</option>';
      }
      refreshSelect();
      function draw() {
        const cols = store?.columns || [];
        const rect = canvas.getBoundingClientRect();
        canvas.width = Math.max(320, Math.floor(rect.width * devicePixelRatio));
        canvas.height = Math.max(210, Math.floor(rect.height * devicePixelRatio));
        ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
        const w = rect.width, h = rect.height;
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, w, h);
        const selected = select.value || '__all__';
        const seriesNames = selected === '__all__' ? cols : [selected];
        const x = store?.time || [];
        const allY = seriesNames.flatMap((name) => store?.series?.[name] || []);
        ctx.strokeStyle = '#d9e2df';
        ctx.lineWidth = 1;
        for (let i=0; i<5; i++) {
          const yy = 22 + i * (h - 50) / 4;
          ctx.beginPath(); ctx.moveTo(42, yy); ctx.lineTo(w - 12, yy); ctx.stroke();
        }
        ctx.fillStyle = '#66736f';
        ctx.font = '12px system-ui, sans-serif';
        if (!x.length || !allY.length) {
          ctx.fillText('No series available', 46, h / 2);
          return;
        }
        const finite = allY.filter(Number.isFinite);
        let minY = Math.min(...finite), maxY = Math.max(...finite);
        if (!Number.isFinite(minY) || !Number.isFinite(maxY)) { minY = 0; maxY = 1; }
        if (Math.abs(maxY - minY) < 1e-9) { maxY += 1; minY -= 1; }
        const minX = x[0], maxX = x[x.length - 1] || x[0] + 1;
        const left = 42, right = w - 12, top = 18, bottom = h - 30;
        const sx = (v) => left + ((v - minX) / Math.max(1e-12, maxX - minX)) * (right - left);
        const sy = (v) => bottom - ((v - minY) / (maxY - minY)) * (bottom - top);
        ctx.fillText(maxY.toPrecision(4), 7, top + 4);
        ctx.fillText(minY.toPrecision(4), 7, bottom);
        ctx.fillText('time (s)', Math.max(46, right - 58), h - 8);
        for (const [seriesIdx, name] of seriesNames.entries()) {
          const y = store?.series?.[name] || [];
          ctx.strokeStyle = selected === '__all__' ? palette[seriesIdx % palette.length] : color;
          ctx.globalAlpha = selected === '__all__' ? 0.72 : 1.0;
          ctx.lineWidth = selected === '__all__' ? 1.35 : 2;
          ctx.beginPath();
          let started = false;
          for (let i=0; i<Math.min(x.length, y.length); i++) {
            if (!Number.isFinite(x[i]) || !Number.isFinite(y[i])) { started = false; continue; }
            const px = sx(x[i]), py = sy(y[i]);
            if (!started) { ctx.moveTo(px, py); started = true; }
            else ctx.lineTo(px, py);
          }
          ctx.stroke();
        }
        ctx.globalAlpha = 1.0;
        if (selected === '__all__') {
          ctx.fillStyle = '#66736f';
          ctx.fillText(`${seriesNames.length} signals`, 46, top + 16);
        }
        if (marker.time.length) {
          const t = marker.time[idx] || 0;
          const px = sx(Math.max(minX, Math.min(maxX, t)));
          ctx.strokeStyle = '#17211e';
          ctx.setLineDash([4, 4]);
          ctx.beginPath(); ctx.moveTo(px, top); ctx.lineTo(px, bottom); ctx.stroke();
          ctx.setLineDash([]);
        }
      }
      select.addEventListener('change', draw);
      addEventListener('resize', draw);
      return { draw, refreshSelect };
    }
    data.ik = data.ik || emptyStore();
    data.id = data.id || emptyStore();
    const ikPlot = makeSeriesPlot('ikPlot', data.ik, 'ikSelect', '#0f766e');
    const idPlot = makeSeriesPlot('idPlot', data.id, 'idSelect', '#d65a31');
    const drawIk = ikPlot.draw;
    const drawId = idPlot.draw;

    function applyEmbeddedPayload(embedded) {
      if (!embedded || typeof embedded !== 'object') return;
      data.title = embedded.title || data.title;
      data.force_scale = embedded.force_scale || data.force_scale || 0.35;
      Object.assign(marker, embedded.markers || emptyMarkers());
      Object.assign(body, embedded.bodies || emptyBodies());
      Object.assign(force, embedded.forces || {names:[], frames:[]});
      Object.assign(data.ik, embedded.ik || emptyStore());
      Object.assign(data.id, embedded.id || emptyStore());
      if (force?.diagnostics?.warning) notice.textContent = force.diagnostics.warning;
      else notice.textContent = 'GLB metadata loaded. Model motion, forces, IK, and inverse dynamics are synchronized.';
      rebuildMarkerScene();
      rebuildBodyScene();
      syncTimeline();
      refreshStats();
      ikPlot.refreshSelect();
      idPlot.refreshSelect();
    }

    function animate(now) {
      requestAnimationFrame(animate);
      resizeRenderer();
      if (playing && timelineFrames) {
        if (!lastTick) lastTick = now;
        const elapsed = now - lastTick;
        const stepMs = 45 / Number(speedSelect.value || 1);
        if (elapsed >= stepMs) {
          updateFrame(idx + Math.max(1, Math.floor(elapsed / stepMs)));
          drawIk(); drawId();
          lastTick = now;
        }
      } else {
        lastTick = now;
      }
      controls.update();
      renderer.render(scene, camera);
    }
    updateFrame(0);
    frameScene();
    drawIk(); drawId();
    animate();
  </script>
</body>
</html>
"""
    html = html.replace("__TITLE__", safe_title).replace("__PAYLOAD__", payload_json)
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
    embed_glb: bool = False,
) -> OpenSimVisualizerResult:
    """Write a notebook-ready HTML dashboard for IK, ID, forces, and 3D motion."""

    html_path = Path(html_path).expanduser().resolve()
    if marker_dataframe is None:
        if osim_path is None or ik_path is None:
            raise ValueError("Provide marker_dataframe or both osim_path and ik_path.")
        marker_stride = _auto_visualizer_stride(
            ik_path,
            max_frames=max_frames,
            requested_stride=marker_stride,
        )
        marker_dataframe = extract_opensim_marker_positions(
            osim_path=osim_path,
            mot_path=ik_path,
            stride=marker_stride,
        )
    markers = _marker_payload(marker_dataframe, max_frames=max_frames)
    forces = _external_load_payload(
        external_loads_path,
        target_time=markers["time"],
        osim_path=osim_path,
        ik_path=ik_path,
    )

    glb_ref = None
    glb_source = None
    if glb_path is not None:
        glb = Path(glb_path).expanduser().resolve()
        if glb.is_file():
            glb_source = str(glb)
            glb_ref = _asset_reference(glb, html_path.parent, embed=embed_glb)

    payload = _empty_visualizer_payload(title=title, glb_path=glb_ref)
    payload.update(
        {
            "markers": markers,
            "bodies": _body_transform_payload(
                osim_path=osim_path,
                ik_path=ik_path,
                target_time=markers["time"],
            ),
            "forces": forces,
            "ik": _storage_for_visualizer(ik_path),
            "id": _storage_for_visualizer(id_path),
        }
    )
    _write_visualizer_html(html_path, title=title, payload=payload)
    metadata = {
        "html_path": str(html_path),
        "glb_path": glb_source,
        "embedded_glb": bool(glb_ref and glb_ref.startswith("data:")),
        "marker_frames": len(markers["frames"]),
        "marker_count": len(markers["names"]),
        "force_count": 0 if forces is None else len(forces["names"]),
        "ik_path": None if ik_path is None else str(Path(ik_path).expanduser().resolve()),
        "id_path": None if id_path is None else str(Path(id_path).expanduser().resolve()),
        "external_loads_path": None
        if external_loads_path is None
        else str(Path(external_loads_path).expanduser().resolve()),
    }
    return OpenSimVisualizerResult(
        html_path=html_path,
        metadata=metadata,
        marker_dataframe=marker_dataframe,
    )


def save_opensim_fast_visualizer(
    html_path: str | Path,
    *,
    osim_path: str | Path,
    ik_path: str | Path,
    id_path: str | Path | None = None,
    external_loads_path: str | Path | None = None,
    marker_dataframe: pd.DataFrame | None = None,
    title: str = "monomech fast IK and ID visualizer",
    max_frames: int = 240,
    marker_stride: int = 1,
) -> OpenSimVisualizerResult:
    """Write the fast OpenSim HTML viewer without exporting or loading a GLB.

    The fast viewer uses OpenSim body transforms to animate lightweight body
    proxies, markers, force arrows, IK traces, and ID traces. Use
    `save_opensim_animation()` when full anatomical surface meshes are needed.
    """

    return save_opensim_visualizer(
        html_path,
        osim_path=osim_path,
        ik_path=ik_path,
        id_path=id_path,
        external_loads_path=external_loads_path,
        glb_path=None,
        marker_dataframe=marker_dataframe,
        title=title,
        max_frames=max_frames,
        marker_stride=marker_stride,
        embed_glb=False,
    )


def save_opensim_glb(**kwargs) -> OpenSimAnimationResult:
    """Alias for `save_opensim_animation()` when the goal is only the GLB file."""

    return save_opensim_animation(**kwargs)


def show_ik_animation(html_path: str | Path, glb_path: str | Path) -> Path:
    """Compatibility helper that writes an HTML viewer for an IK animation."""

    return save_animation_viewer(html_path, glb_path)
