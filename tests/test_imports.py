from pathlib import Path

import tomllib

import monomech as mm


def test_public_api():
    assert hasattr(mm, "load_video")
    assert hasattr(mm, "load_trc")
    assert hasattr(mm, "external")
    assert hasattr(mm, "save_opensim_animation")
    assert hasattr(mm, "save_ik_animation")
    assert hasattr(mm, "pose_to_trc")
    assert hasattr(mm, "markers_to_id")
    assert hasattr(mm, "video_to_id")


def test_native_dependencies_are_optional():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    dependencies = "\n".join(pyproject["project"]["dependencies"])
    extras = pyproject["project"]["optional-dependencies"]

    assert "mediapipe" not in dependencies
    assert "opencv-python-headless" not in dependencies
    assert "pyopensim" not in dependencies
    assert "pyvista" not in dependencies
    assert "pygltflib" not in dependencies
    assert "numpy>=1.26,<2" in dependencies
    assert {"pose", "opensim", "animation", "all"} <= set(extras)
