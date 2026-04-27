from pathlib import Path

import numpy as np
import pandas as pd

import monomech as mm
from monomech.animation import _dedupe_geometry_specs, _geometry_file_aliases


def test_animation_viewer_uses_relative_glb(tmp_path):
    glb = tmp_path / "motion.glb"
    glb.write_bytes(b"glb")
    html = mm.save_animation_viewer(tmp_path / "viewer.html", glb, title="Test animation")

    text = html.read_text(encoding="utf-8")
    assert '"glb_path": "data:model/gltf-binary;base64,' in text
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
    assert "All signals" in text
    assert "external forces" in text
    assert "model bone overlay" not in text
    assert "modelSkeletonGroup" not in text
    assert result.metadata["force_count"] == 1


def test_opensim_visualizer_references_glb_by_default(tmp_path):
    markers = pd.DataFrame(
        {
            "hip_r_x": [0.0],
            "hip_r_y": [0.0],
            "hip_r_z": [0.0],
        },
        index=pd.Index([0.0], name="time"),
    )
    glb_path = tmp_path / "motion.glb"
    glb_path.write_bytes(b"glb")

    result = mm.save_opensim_visualizer(
        tmp_path / "viewer.html",
        marker_dataframe=markers,
        glb_path=glb_path,
    )

    text = result.html_path.read_text(encoding="utf-8")
    assert '"glb_path": "motion.glb"' in text
    assert "data:model/gltf-binary;base64" not in text
    assert result.metadata["embedded_glb"] is False


def test_animate_exposes_speed_and_reference_options(monkeypatch, tmp_path):
    ik_path = tmp_path / "trial_ik.mot"
    ik_path.write_text("endheader\ntime pelvis_tx\n0.0 0.0\n", encoding="utf-8")
    model_path = tmp_path / "model.osim"
    model_path.write_text("<OpenSimDocument />", encoding="utf-8")
    captured = {}

    def fake_animation(**kwargs):
        captured["animation"] = kwargs

        class Result:
            glb_path = kwargs["out_glb_path"]

        Result.glb_path.write_bytes(b"glb")
        return Result()

    def fake_visualizer(html_path, **kwargs):
        captured["visualizer"] = {"html_path": html_path, **kwargs}
        html_path = Path(html_path)
        html_path.write_text("viewer", encoding="utf-8")
        return mm.OpenSimVisualizerResult(html_path=html_path, metadata=kwargs)

    monkeypatch.setattr("monomech.api.save_opensim_animation", fake_animation)
    monkeypatch.setattr("monomech.api.save_opensim_visualizer", fake_visualizer)
    monkeypatch.setattr("monomech.api.get_builtin_geometry_dir", lambda: tmp_path)

    result = mm.animate(
        ik=ik_path,
        model=model_path,
        output_dir=tmp_path / "viz",
        mode="preview",
        stride=4,
        decimate_target_reduction=0.25,
        embed_glb=False,
    )

    assert result.html_path.name == "trial.html"
    assert captured["animation"]["stride"] == 4
    assert captured["animation"]["decimate_target_reduction"] == 0.25
    assert captured["visualizer"]["embed_glb"] is False
    assert captured["visualizer"]["max_frames"] == 160


def test_visualizer_keeps_all_storage_signals(tmp_path):
    times = np.array([0.0, 0.5, 1.0])
    markers = pd.DataFrame(
        {
            "hip_r_x": [0.0, 0.1, 0.2],
            "hip_r_y": [0.0, 0.0, 0.0],
            "hip_r_z": [0.0, 0.0, 0.0],
        },
        index=pd.Index(times, name="time"),
    )
    ik_path = tmp_path / "many.mot"
    cols = ["time", *[f"coord_{i}" for i in range(20)]]
    rows = [" ".join(cols)]
    for t in times:
        rows.append(" ".join([str(t), *[str(i + t) for i in range(20)]]))
    ik_path.write_text("endheader\n" + "\n".join(rows), encoding="utf-8")

    result = mm.save_opensim_visualizer(
        tmp_path / "viewer.html",
        marker_dataframe=markers,
        ik_path=ik_path,
    )

    text = result.html_path.read_text(encoding="utf-8")
    assert "coord_0" in text
    assert "coord_19" in text
    assert "All signals (${cols.length})" in text


def test_geometry_aliases_cover_full_body_model_variants():
    assert "r_femur.vtp" in _geometry_file_aliases("femur_r.vtp")
    assert "l_tibia.vtp" in _geometry_file_aliases("tibia_lv.vtp")
    assert "r_talus.vtp" in _geometry_file_aliases("talus_rv.vtp")
    assert "hat_spine.vtp" in _geometry_file_aliases("thoracic1_s.vtp")
    assert "hat_spine.vtp" in _geometry_file_aliases("lumbar5.vtp")


def test_geometry_specs_prefer_body_owned_meshes():
    specs = [
        {
            "mesh_file": "femur_r.vtp",
            "frame_path": None,
            "body_owner": None,
            "scale": None,
        },
        {
            "mesh_file": "femur_r.vtp",
            "frame_path": None,
            "body_owner": "femur_r",
            "scale": None,
        },
    ]

    kept = _dedupe_geometry_specs(specs)

    assert len(kept) == 1
    assert kept[0]["body_owner"] == "femur_r"
