from pathlib import Path

import monomech as mm


def test_builtin_osim_model_strips_missing_mesh_geometry(tmp_path: Path):
    model_path = mm.get_builtin_osim_model("pose", extract_dir=tmp_path)

    text = model_path.read_text(encoding="utf-8")
    assert model_path.name == "Mediapipe_nogeometry.osim"
    assert "<Mesh" not in text
    assert ".vtp" not in text


def test_builtin_osim_model_can_include_original_geometry(tmp_path: Path):
    model_path = mm.get_builtin_osim_model("pose", extract_dir=tmp_path, include_geometry=True)

    text = model_path.read_text(encoding="utf-8")
    assert model_path.name == "Mediapipe.osim"
    assert "<Mesh" in text


def test_builtin_geometry_dir_is_available(tmp_path: Path):
    geometry_dir = mm.get_builtin_geometry_dir(extract_dir=tmp_path)

    assert geometry_dir.is_dir()
    assert (geometry_dir / "hat_spine.vtp").is_file()
    assert (geometry_dir / "r_femur.vtp").is_file()
