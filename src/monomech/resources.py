from __future__ import annotations

from contextlib import contextmanager
from importlib.resources import as_file, files
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET
from typing import Iterator


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
    include_geometry: bool = False,
) -> Path:
    """
    Return a stable filesystem path to a packaged OpenSim model.

    This avoids requiring users to use a `with` statement by copying the
    packaged model into a cache directory the first time it is requested.
    """
    filename = _resolve_builtin_osim_filename(name)

    if extract_dir is None:
        extract_dir = Path(tempfile.gettempdir()) / "monomech_models"
    else:
        extract_dir = Path(extract_dir)

    extract_dir.mkdir(parents=True, exist_ok=True)
    resolved_filename = filename if include_geometry else f"{Path(filename).stem}_nogeometry{Path(filename).suffix}"
    out_path = extract_dir / resolved_filename

    if not out_path.exists():
        resource = files("monomech.data") / filename
        with as_file(resource) as src:
            shutil.copy2(src, out_path)
        if not include_geometry:
            _strip_opensim_mesh_geometry(out_path)

    return out_path


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
