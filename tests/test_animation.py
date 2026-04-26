from pathlib import Path

import numpy as np
import pandas as pd

import monomech as mm


def test_animation_viewer_uses_relative_glb(tmp_path):
    glb = tmp_path / "motion.glb"
    glb.write_bytes(b"glb")
    html = mm.save_animation_viewer(tmp_path / "viewer.html", glb, title="Test animation")

    text = html.read_text(encoding="utf-8")
    assert '"glb_path": "motion.glb"' in text
    assert "GLTFLoader" in text
    assert "Upload GLB" in text
    assert "Test animation" in text


def test_animation_extra_is_optional():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "pyvista" not in pyproject.split("[project.optional-dependencies]")[0]
    assert "pygltflib" not in pyproject.split("[project.optional-dependencies]")[0]


def test_opensim_visualizer_writes_dashboard_without_glb(tmp_path):
    times = np.array([0.0, 0.5, 1.0])
    markers = pd.DataFrame(
        {
            "hip_r_x": [0.0, 0.1, 0.2],
            "hip_r_y": [0.0, 0.0, 0.0],
            "hip_r_z": [0.0, 0.0, 0.0],
            "knee_r_x": [0.0, 0.1, 0.2],
            "knee_r_y": [-0.4, -0.4, -0.4],
            "knee_r_z": [0.0, 0.0, 0.0],
            "ankle_r_x": [0.0, 0.1, 0.2],
            "ankle_r_y": [-0.8, -0.8, -0.8],
            "ankle_r_z": [0.0, 0.0, 0.0],
        },
        index=pd.Index(times, name="time"),
    )
    ik_path = tmp_path / "ik.mot"
    ik_path.write_text(
        "endheader\n"
        "time pelvis_tilt knee_angle_r\n"
        "0.0 1.0 2.0\n"
        "0.5 1.5 2.5\n"
        "1.0 2.0 3.0\n",
        encoding="utf-8",
    )
    id_path = tmp_path / "id.sto"
    id_path.write_text(
        "endheader\n"
        "time pelvis_tx_force knee_angle_r_moment\n"
        "0.0 10.0 20.0\n"
        "0.5 11.0 21.0\n"
        "1.0 12.0 22.0\n",
        encoding="utf-8",
    )
    forces_path = tmp_path / "loads.mot"
    forces_path.write_text(
        "endheader\n"
        "time right_vx right_vy right_vz right_px right_py right_pz\n"
        "0.0 0.0 100.0 0.0 0.0 -0.8 0.0\n"
        "0.5 0.0 120.0 0.0 0.1 -0.8 0.0\n"
        "1.0 0.0 90.0 0.0 0.2 -0.8 0.0\n",
        encoding="utf-8",
    )

    result = mm.save_opensim_visualizer(
        tmp_path / "viewer.html",
        marker_dataframe=markers,
        ik_path=ik_path,
        id_path=id_path,
        external_loads_path=forces_path,
        title="Unit test viewer",
    )

    text = result.html_path.read_text(encoding="utf-8")
    assert "Three.js model playback" in text
    assert "Upload GLB" in text
    assert "pelvis_tilt" in text
    assert "knee_angle_r_moment" in text
    assert "external forces" in text
    assert result.metadata["force_count"] == 1
