from pathlib import Path

import numpy as np
import pandas as pd

import monomech as mm
from monomech.io.storage import read_storage
from monomech.io.trc import load_trc, write_trc
from monomech.opensim_api import (
    _prepare_storage_for_opensim,
    _prepare_trc_for_opensim,
    _read_storage_time_vector,
    _summarize_ik_marker_errors,
    _write_external_loads_data,
)


def test_prepare_trc_for_opensim_fills_marker_nans(tmp_path: Path):
    trc_path = tmp_path / "raw.trc"
    data = np.array(
        [
            [[0.0, 1.0, 2.0]],
            [[np.nan, 2.0, 3.0]],
            [[2.0, np.nan, 4.0]],
        ],
        dtype=float,
    )

    write_trc(
        trc_path,
        time=np.array([0.0, 0.5, 1.0]),
        data=data,
        marker_names=["heel"],
        units="m",
        fps=2.0,
    )

    prepared, report = _prepare_trc_for_opensim(
        trc_path,
        output_dir=tmp_path,
        prefix="raw",
        sanitize=True,
    )

    assert prepared != trc_path
    assert report["sanitized"] is True
    assert report["input_nan_count"] == 2
    clean = load_trc(prepared)
    assert np.isfinite(clean.markers.data).all()


def test_prepare_storage_for_opensim_fills_coordinate_nans(tmp_path: Path):
    storage_path = tmp_path / "ik.mot"
    storage_path.write_text(
        "\n".join(
            [
                "name ik",
                "datacolumns 3",
                "datarows 3",
                "range 0.000000 1.000000",
                "endheader",
                "time\thip_flexion\tknee_angle",
                "0.0\t1.0\t2.0",
                "0.5\tnan\t3.0",
                "1.0\t5.0\tnan",
            ]
        ),
        encoding="utf-8",
    )

    prepared, report = _prepare_storage_for_opensim(
        storage_path,
        output_dir=tmp_path,
        prefix="ik",
        sanitize=True,
    )

    assert prepared != storage_path
    assert report["sanitized"] is True
    clean = read_storage(prepared)
    assert np.isfinite(clean.to_numpy(dtype=float)).all()


def test_external_load_resampling_removes_nans(tmp_path: Path):
    loads = mm.external.from_dataframe(
        df=pd.DataFrame(
            {
                "time": [0.0, 0.5, 1.0],
                "Fx": [0.0, np.nan, 0.0],
                "Fy": [10.0, 20.0, np.nan],
                "Fz": [0.0, 0.0, 0.0],
                "Px": [0.0, np.nan, 0.0],
                "Py": [0.0, 0.0, 0.0],
                "Pz": [0.0, 0.0, 0.0],
            }
        ),
        applied_to_body="calcn_r",
        force_columns=("Fx", "Fy", "Fz"),
        point_columns=("Px", "Py", "Pz"),
        name="right_grf",
    )

    mot_path, xml_path = _write_external_loads_data(
        loads,
        tmp_path,
        "trial",
        time_vector=np.array([0.0, 0.25, 0.5, 0.75, 1.0]),
    )

    assert mot_path.exists()
    assert xml_path.exists()
    table = read_storage(mot_path)
    numeric = table.drop(columns=["time"]).to_numpy(dtype=float)
    assert np.isfinite(numeric).all()


def test_full_trial_external_load_expands_to_ik_time(tmp_path: Path):
    load = mm.load(type="carried", body="hand_r", mass_kg=10.0)

    mot_path, xml_path = _write_external_loads_data(
        load,
        tmp_path,
        "trial",
        time_vector=np.array([2.0, 2.5, 3.0]),
    )

    table = read_storage(mot_path)
    assert np.allclose(table["time"], [2.0, 2.5, 3.0])
    assert np.allclose(table["carried_load_vy"], -98.1)
    xml = xml_path.read_text(encoding="utf-8")
    assert "<applied_to_body>hand_r</applied_to_body>" in xml
    assert "<point_expressed_in_body>hand_r</point_expressed_in_body>" in xml


def test_explicit_external_load_window_stays_time_limited(tmp_path: Path):
    load = mm.load(
        type="constant",
        body="hand_r",
        force=(0.0, -10.0, 0.0),
        start_time=2.25,
        end_time=2.75,
    )

    mot_path, _ = _write_external_loads_data(
        load,
        tmp_path,
        "trial",
        time_vector=np.array([2.0, 2.5, 3.0]),
    )

    table = read_storage(mot_path)
    assert np.allclose(table["constant_load_vy"], [0.0, -10.0, 0.0])


def test_read_storage_time_vector_handles_padded_opensim_rows(tmp_path: Path):
    storage_path = tmp_path / "ik.mot"
    storage_path.write_text(
        "\n".join(
            [
                "Coordinates",
                "version=1",
                "nRows=2",
                "nColumns=3",
                "inDegrees=yes",
                "endheader",
                "time\tpelvis_tilt\tpelvis_tx",
                "      0.00000000\t    189.89380616\t      2.05699634",
                "      0.03372100\t    182.98767450\t      1.91619641",
            ]
        ),
        encoding="utf-8",
    )

    time = _read_storage_time_vector(storage_path)

    assert np.allclose(time, [0.0, 0.033721])


def test_estimated_grf_points_use_opensim_axes():
    pose = type(
        "Pose",
        (),
        {
            "time": np.array([0.0, 0.5]),
            "landmark_names": ["left_heel", "left_foot_index", "left_ankle"],
            "data": np.array(
                [
                    [[1.0, 2.0, 3.0], [1.2, 2.1, 3.2], [1.1, 2.2, 3.1]],
                    [[1.4, 2.4, 3.4], [1.6, 2.5, 3.6], [1.5, 2.6, 3.5]],
                ]
            ),
        },
    )()

    loads = mm.external.estimate_grf(pose3d=pose, sides=("left",), body_mass_kg=75.0)

    point = loads[0].data[["Px", "Py", "Pz"]].to_numpy(dtype=float)
    assert np.allclose(point[0], [3.1, 0.1, 1.1])


def test_summarize_ik_marker_errors(tmp_path: Path):
    marker_errors = tmp_path / "_ik_marker_errors.sto"
    marker_errors.write_text(
        "\n".join(
            [
                "Model Marker Errors from IK",
                "version=1",
                "nRows=2",
                "nColumns=4",
                "inDegrees=no",
                "endheader",
                "time\ttotal_squared_error\tmarker_error_RMS\tmarker_error_max",
                "0.0\t0.25\t0.10\t0.30",
                "0.5\t0.09\t0.20\t0.25",
            ]
        ),
        encoding="utf-8",
    )

    summary = _summarize_ik_marker_errors(tmp_path)

    assert summary is not None
    assert summary["rows"] == 2
    assert summary["marker_error_RMS"]["max"] == 0.2
    assert summary["worst_rms_time"] == 0.5
