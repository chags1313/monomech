from pathlib import Path

import numpy as np
import pandas as pd

import monomech as mm
from monomech.results import OpenSimScaleResult, Pose3DGlobalResult, StorageResult


def _pose_with_gap() -> Pose3DGlobalResult:
    data = np.zeros((5, 4, 3), dtype=float)
    data[:, 0, 0] = np.arange(5, dtype=float)
    data[:, 1, 0] = np.arange(5, dtype=float) + 1.0
    data[:, 2, 1] = 1.0
    data[:, 3, 0] = 1.0
    data[:, 3, 1] = 1.0
    data[2, 0, 0] = np.nan
    return Pose3DGlobalResult(
        name="pose",
        data=data,
        time=np.arange(5, dtype=float) / 30.0,
        landmark_names=["left_hip", "right_hip", "left_shoulder", "right_shoulder"],
        dims=("x_m", "y_m", "z_m"),
        fps=30.0,
    )


def test_smooth_and_gap_fill_top_level_work_on_pose_results():
    pose = _pose_with_gap()

    filled = mm.gap_fill(pose, max_gap_frames=3)
    smoothed = mm.smooth(filled, cutoff_hz=6.0)

    assert np.isfinite(filled.data[2, 0, 0])
    assert smoothed.data.shape == pose.data.shape
    assert smoothed is not filled


def test_pose_preview_defaults_are_light_and_y_up():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pose = _pose_with_gap().gap_fill(max_gap_frames=3)

    ax2 = pose.vis_2d(show=False)
    assert ax2.get_facecolor() == (1.0, 1.0, 1.0, 1.0)
    assert not ax2.yaxis_inverted()
    assert len(ax2.lines) >= 3

    ax3 = pose.vis_3d(show=False)
    assert ax3.get_facecolor() == (1.0, 1.0, 1.0, 1.0)
    assert ax3.get_zlabel() == "Y"
    assert ax3.get_ylabel() == "Z"
    assert len(ax3.lines) >= 3
    plt.close("all")


def test_pose_preview_can_overlay_source_image():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pose = _pose_with_gap().gap_fill(max_gap_frames=3)
    image = np.ones((120, 160, 3), dtype=float)

    ax = pose.vis_2d(frame=0, image=image, show=False)

    assert len(ax.images) == 1
    assert ax.get_xlim() == (0.0, 160.0)
    assert ax.yaxis_inverted()
    plt.close("all")


def test_load_and_external_forces_helpers_are_concise():
    dumbbell = mm.load(type="carried", body="hand_r", mass_kg=10.0)
    forces = mm.external_forces(loads=[dumbbell], include_estimated_grf=True)

    assert dumbbell.applied_to_body == "hand_r"
    assert np.isclose(dumbbell.data["Fy"].iloc[0], -98.1)
    assert forces[0] == "estimate"
    assert forces[1] is dumbbell


def test_run_ik_accepts_scaled_model_metadata(monkeypatch, tmp_path):
    trc_path = tmp_path / "trial.trc"
    trc_path.write_text("placeholder", encoding="utf-8")
    model_path = tmp_path / "scaled.osim"
    model_path.write_text("<OpenSimDocument />", encoding="utf-8")

    scaled = OpenSimScaleResult(
        scaled_model_path=model_path,
        metadata={"trc_path": str(trc_path)},
    )

    def fake_run_ik(*, trc_path, model_path, output_dir, config=None):
        del config
        return StorageResult(
            path=Path(output_dir) / "trial_ik.mot",
            dataframe=pd.DataFrame(
                {"time": [0.0, 1.0], "hip_flexion": [0.0, 1.0]}
            ),
            metadata={"trc_path": str(trc_path), "model_path": str(model_path)},
        )

    monkeypatch.setattr("monomech.api._opensim_run_ik", fake_run_ik)

    ik = mm.run_ik(scaled, output_dir=tmp_path / "ik")

    assert ik.metadata["model_path"] == str(model_path)
    assert ik.metadata["trc_path"] == str(trc_path)
