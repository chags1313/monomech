import monomech as mm
import tomllib
from pathlib import Path


def test_public_api():
    assert hasattr(mm, "load_video")
    assert hasattr(mm, "load_trc")
    assert hasattr(mm, "external")


def test_native_dependencies_are_optional():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    dependencies = "\n".join(pyproject["project"]["dependencies"])
    extras = pyproject["project"]["optional-dependencies"]

    assert "mediapipe" not in dependencies
    assert "opencv-python-headless" not in dependencies
    assert "pyopensim" not in dependencies
    assert {"pose", "opensim", "all"} <= set(extras)
