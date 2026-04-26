from pathlib import Path

import monomech as mm


def test_animation_viewer_uses_relative_glb(tmp_path):
    glb = tmp_path / "motion.glb"
    glb.write_bytes(b"glb")
    html = mm.save_animation_viewer(tmp_path / "viewer.html", glb, title="Test animation")

    text = html.read_text(encoding="utf-8")
    assert 'src="motion.glb"' in text
    assert "model-viewer" in text
    assert "Test animation" in text


def test_animation_extra_is_optional():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "pyvista" not in pyproject.split("[project.optional-dependencies]")[0]
    assert "pygltflib" not in pyproject.split("[project.optional-dependencies]")[0]
