from pathlib import Path

import numpy as np
import pandas as pd

import monomech as mm
from monomech.animation import (
    _auto_visualizer_stride,
    _dedupe_geometry_specs,
    _external_load_payload,
    _geometry_file_aliases,
    _inline_notebook_visualizer_html,
    _notebook_file_url,
)


def test_animation_viewer_uses_relative_glb(tmp_path):
    glb = tmp_path / "motion.glb"
    glb.write_bytes(b"glb")
    html = mm.save_animation_viewer(tmp_path / "viewer.html", glb, title="Test animation")

    text = html.read_text(encoding="utf-8")
    assert '"glb_path": "motion.glb"' in text
    assert "data:model/gltf-binary;base64" not in text
    assert "GLTFLoader" in text
    assert "Upload GLB" in text
    assert "Test animation" in text


def test_create_glb_viewer_returns_notebook_result(tmp_path):
    glb = tmp_path / "motion.glb"
    glb.write_bytes(b"glb")

    viewer = mm.create_glb_viewer(glb)

    assert viewer.html_path.name == "motion.viewer.html"
    assert viewer.metadata["glb_path"] == str(glb)
    assert viewer.metadata["embedded_glb"] is False
    text = viewer.html_path.read_text(encoding="utf-8")
    assert '"glb_path": "motion.glb"' in text


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
    assert "Fast OpenSim body playback" in text
    assert "Upload GLB" in text
    assert "pelvis_tilt" in text
    assert "knee_angle_r_moment" in text
    assert "All signals" in text
    assert "external forces" in text
    assert "body proxies" in text
    assert "Fast body viewer ready" in text
    assert "model bone overlay" not in text
    assert "modelSkeletonGroup" not in text
    assert result.metadata["force_count"] == 1


def test_external_load_payload_preserves_body_local_load_metadata(tmp_path):
    forces_path = tmp_path / "trial_external_loads.mot"
    forces_path.write_text(
        "endheader\n"
        "time carried_load_vx carried_load_vy carried_load_vz "
        "carried_load_px carried_load_py carried_load_pz\n"
        "0.0 0.0 -98.1 0.0 0.0 0.0 0.0\n"
        "1.0 0.0 -98.1 0.0 0.0 0.0 0.0\n",
        encoding="utf-8",
    )
    (tmp_path / "trial_ExternalLoads.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8'?>
<OpenSimDocument Version="40000">
  <ExternalLoads name="ExternalLoads">
    <objects>
      <ExternalForce name="carried_load">
        <applied_to_body>hand_r</applied_to_body>
        <force_expressed_in_body>/ground</force_expressed_in_body>
        <point_expressed_in_body>hand_r</point_expressed_in_body>
        <force_identifier>carried_load_v</force_identifier>
        <point_identifier>carried_load_p</point_identifier>
        <torque_identifier>carried_load_t</torque_identifier>
      </ExternalForce>
    </objects>
  </ExternalLoads>
</OpenSimDocument>
""",
        encoding="utf-8",
    )

    payload = _external_load_payload(forces_path, target_time=[0.0, 1.0])

    assert payload is not None
    frame_load = payload["frames"][0][0]
    assert frame_load["applied_to_body"] == "hand_r"
    assert frame_load["point_expressed_in"] == "hand_r"
    assert frame_load["force_expressed_in"] == "/ground"
    assert frame_load["raw_point"] == [0.0, 0.0, 0.0]
    assert "body-local" in payload["diagnostics"]["warning"]


def test_visualizer_stride_auto_caps_opensim_extraction(tmp_path):
    ik_path = tmp_path / "long_ik.mot"
    rows = ["endheader", "time pelvis_tx"]
    rows.extend(f"{i / 100:.2f} {i * 0.001:.4f}" for i in range(1000))
    ik_path.write_text("\n".join(rows), encoding="utf-8")

    stride = _auto_visualizer_stride(ik_path, max_frames=100, requested_stride=1)

    assert stride == 10


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


def test_visualizer_repr_uses_fast_file_iframe_by_default(tmp_path):
    result = mm.OpenSimVisualizerResult(
        html_path=Path.cwd() / "outputs" / "viewer.html",
        metadata={},
    )

    html = result._repr_html_()

    assert 'src="/files/outputs/viewer.html"' in html
    assert "MONOMECH_GLB_BASE64" not in html


def test_inline_notebook_visualizer_can_inject_glb_when_requested(tmp_path):
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

    html = _inline_notebook_visualizer_html(result.html_path, result.metadata)

    assert "window.MONOMECH_GLB_BASE64" in html
    assert "loadGlb(url)" in html
    assert "if (!window.MONOMECH_GLB_BASE64 && data.glb_path) loadGlb(data.glb_path);" in html
    assert "Z2xi" in html


def test_inline_simple_glb_viewer_skips_path_autoload(tmp_path):
    glb_path = tmp_path / "motion.glb"
    glb_path.write_bytes(b"glb")
    viewer = mm.create_glb_viewer(glb_path)

    html = _inline_notebook_visualizer_html(viewer.html_path, viewer.metadata)

    assert "window.MONOMECH_GLB_BASE64" in html
    assert "if (!window.MONOMECH_GLB_BASE64 && data.glb_path) loadGlb(data.glb_path);" in html
    assert "if (data.glb_path) loadGlb(data.glb_path);" not in html


def test_glb_viewer_can_create_upload_first_base_viewer(tmp_path):
    viewer = mm.glb_viewer(html_path=tmp_path / "base.html")

    text = viewer.html_path.read_text(encoding="utf-8")
    assert viewer.metadata["glb_path"] is None
    assert '"glb_path": null' in text
    assert "Upload GLB" in text
    assert "3D Model, Markers, And Forces" in text


def test_colab_display_uses_inline_html(monkeypatch, tmp_path):
    viewer = mm.glb_viewer(html_path=tmp_path / "base.html")
    captured = {}

    class FakeHTML:
        def __init__(self, html):
            self.html = html

    class FakeIFrame:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Colab display should not use file iframe")

    def fake_display(frame):
        captured["frame"] = frame

    monkeypatch.setattr("monomech.animation._running_in_colab", lambda: True)
    monkeypatch.setitem(
        __import__("sys").modules,
        "IPython.display",
        type(
            "FakeDisplayModule",
            (),
            {"HTML": FakeHTML, "IFrame": FakeIFrame, "display": staticmethod(fake_display)},
        ),
    )

    frame = viewer.show()

    assert frame is captured["frame"]
    assert "Upload GLB" in frame.html
    assert "localhost" not in frame.html


def test_notebook_file_url_falls_back_for_paths_outside_cwd(tmp_path):
    outside = tmp_path / "viewer.html"
    outside.write_text("viewer", encoding="utf-8")

    assert _notebook_file_url(outside).startswith("file:///")


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
            marker_dataframe = pd.DataFrame(
                {"hip_r_x": [0.0], "hip_r_y": [0.0], "hip_r_z": [0.0]},
                index=pd.Index([0.0], name="time"),
            )

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
    assert captured["visualizer"]["marker_dataframe"] is not None


def test_animate_fast_render_skips_glb_export(monkeypatch, tmp_path):
    ik_path = tmp_path / "trial_ik.mot"
    ik_path.write_text("endheader\ntime pelvis_tx\n0.0 0.0\n", encoding="utf-8")
    model_path = tmp_path / "model.osim"
    model_path.write_text("<OpenSimDocument />", encoding="utf-8")
    captured = {"animation_called": False}

    def fake_animation(**kwargs):
        captured["animation_called"] = True
        raise AssertionError("fast render should not export GLB")

    def fake_visualizer(html_path, **kwargs):
        captured["visualizer"] = {"html_path": html_path, **kwargs}
        html_path = Path(html_path)
        html_path.write_text("viewer", encoding="utf-8")
        return mm.OpenSimVisualizerResult(html_path=html_path, metadata=kwargs)

    monkeypatch.setattr("monomech.api.save_opensim_animation", fake_animation)
    monkeypatch.setattr("monomech.api.save_opensim_visualizer", fake_visualizer)

    result = mm.animate(
        ik=ik_path,
        model=model_path,
        output_dir=tmp_path / "viz",
        render="fast",
    )

    assert result.html_path.name == "trial.html"
    assert captured["animation_called"] is False
    assert captured["visualizer"]["glb_path"] is None
    assert captured["visualizer"]["max_frames"] == 120


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
