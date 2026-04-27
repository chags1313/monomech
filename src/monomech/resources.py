from __future__ import annotations

import shutil
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import as_file, files
from pathlib import Path

_BUILTIN_OSIM_MODELS = {
    "pose": "Mediapipe.osim",
    "mocap": "ViconFullBody.osim",
}


def list_builtin_osim_models() -> dict[str, str]:
    return dict(_BUILTIN_OSIM_MODELS)


def _resolve_builtin_osim_filename(name: str) -> str:
    return _BUILTIN_OSIM_MODELS.get(name, name)


@contextmanager
def builtin_osim_model_path(name: str = "pose") -> Iterator[Path]:
    """
    Low-level context-managed access to a packaged OpenSim model.
    Supported names:
      - 'pose'  -> Mediapipe.osim
      - 'mocap' -> ViconFullBody.osim
    """
    filename = _resolve_builtin_osim_filename(name)
    resource = files("monomech.data") / filename
    with as_file(resource) as path:
        yield Path(path)


def get_builtin_osim_model(
    name: str = "pose",
    *,
    extract_dir: str | Path | None = None,
    include_geometry: bool = True,
) -> Path:
    """
    Return a stable filesystem path to a packaged OpenSim model.

    This avoids requiring users to use a `with` statement by copying the
    packaged model into a cache directory the first time it is requested. By
    default the original model display geometry references are preserved so
    animation export can resolve every mesh from the packaged geometry folder.
    """
    filename = _resolve_builtin_osim_filename(name)

    if extract_dir is None:
        extract_dir = Path(tempfile.gettempdir()) / "monomech_models"
    else:
        extract_dir = Path(extract_dir)

    extract_dir.mkdir(parents=True, exist_ok=True)
    model_name = Path(filename)
    resolved_filename = (
        filename if include_geometry else f"{model_name.stem}_nogeometry{model_name.suffix}"
    )
    out_path = extract_dir / resolved_filename

    if not out_path.exists():
        resource = files("monomech.data") / filename
        with as_file(resource) as src:
            shutil.copy2(src, out_path)
        if not include_geometry:
            _strip_opensim_mesh_geometry(out_path)

    return out_path


def get_builtin_geometry_dir(*, extract_dir: str | Path | None = None) -> Path:
    """Return a stable filesystem path to packaged OpenSim display geometry."""

    if extract_dir is None:
        extract_dir = Path(tempfile.gettempdir()) / "monomech_models"
    else:
        extract_dir = Path(extract_dir)
    out_dir = extract_dir / "Geometry"
    out_dir.mkdir(parents=True, exist_ok=True)

    resource_dir = files("monomech.data") / "Geometry"
    copied_any = False
    for resource in resource_dir.iterdir():
        if not resource.name.lower().endswith(".vtp"):
            continue
        out_path = out_dir / resource.name
        if out_path.exists():
            copied_any = True
            continue
        with as_file(resource) as src:
            shutil.copy2(src, out_path)
        copied_any = True

    if not copied_any:
        raise FileNotFoundError("No packaged OpenSim geometry files were found.")
    return out_dir


def _strip_opensim_mesh_geometry(path: str | Path) -> None:
    """
    Remove mesh display geometry from a copied OpenSim model.

    The packaged model can run without visualization meshes, and removing the
    missing mesh references avoids pages of OpenSim warnings during scale/IK/ID.
    """
    path = Path(path)
    tree = ET.parse(path)
    root = tree.getroot()
    removed = 0
    for parent in root.iter():
        for child in list(parent):
            if child.tag == "Mesh":
                parent.remove(child)
                removed += 1
    if removed:
        tree.write(path, encoding="utf-8", xml_declaration=True)


@contextmanager
def builtin_pose_model_path(name: str = "pose_landmarker_heavy.task") -> Iterator[Path]:
    resource = files("monomech.data") / name
    with as_file(resource) as path:
        yield Path(path)
