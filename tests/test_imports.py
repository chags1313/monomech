from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

import monomech as mm


def test_public_api():
    assert hasattr(mm, "load_video")
    assert hasattr(mm, "load_trc")
    assert hasattr(mm, "external")
    assert hasattr(mm, "save_opensim_animation")
    assert hasattr(mm, "display_visualizer")
    assert hasattr(mm, "save_ik_animation")
    assert hasattr(mm, "pose_to_trc")
    assert hasattr(mm, "markers_to_id")
    assert hasattr(mm, "video_to_id")
    assert hasattr(mm, "video_to_trc")
    assert hasattr(mm, "trc_to_inverse_dynamics")
    assert hasattr(mm, "video_to_inverse_dynamics")
    assert hasattr(mm, "get_builtin_geometry_dir")
    assert hasattr(mm, "estimate_pose")
    assert hasattr(mm, "smooth")
    assert hasattr(mm, "gap_fill")
    assert hasattr(mm, "run_scaling")
    assert hasattr(mm, "run_ik")
    assert hasattr(mm, "load")
    assert hasattr(mm, "estimate_grf")
    assert hasattr(mm, "external_forces")
    assert hasattr(mm, "run_id")
    assert hasattr(mm, "animate")
    assert hasattr(mm, "video_pipeline")
    assert hasattr(mm, "marker_pipeline")


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
