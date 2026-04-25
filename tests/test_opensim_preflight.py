from pathlib import Path

import numpy as np
import pandas as pd

import monomech as mm
from monomech.io.storage import read_storage
from monomech.io.trc import load_trc, write_trc
from monomech.opensim_api import (
    _prepare_storage_for_opensim,
    _prepare_trc_for_opensim,
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
