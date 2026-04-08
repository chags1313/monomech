from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd



def _coerce_time_column(df: pd.DataFrame) -> str:
    for candidate in ("Time", "time"):
        if candidate in df.columns:
            return candidate
    raise ValueError("TRC/marker table must contain a Time or time column.")


def load_trc(path: str | Path, *, name: str | None = None, metadata: dict | None = None):
    path = Path(path)
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        lines = [line.rstrip("\n") for line in f]

    if len(lines) < 5:
        raise ValueError(f"TRC file appears too short: {path}")

    header_3 = lines[2].split("\t")
    header_4 = lines[3].split("\t")
    data_lines = lines[5:]

    marker_names: list[str] = []
    for i in range(2, len(header_4), 3):
        raw = header_4[i].strip()
        if raw:
            marker_names.append(raw)

    columns = ["Frame#", "Time"]
    for marker in marker_names:
        columns.extend([f"{marker}_x", f"{marker}_y", f"{marker}_z"])

    rows: list[list[float | int | None]] = []
    for line in data_lines:
        if not line.strip():
            continue
        tokens = re.split(r"\t+", line.strip())
        if len(tokens) < 2:
            continue
        row: list[float | int | None] = []
        for idx, token in enumerate(tokens[: len(columns)]):
            if idx == 0:
                row.append(int(float(token)))
            else:
                try:
                    row.append(float(token))
                except ValueError:
                    row.append(np.nan)
        if len(row) < len(columns):
            row.extend([np.nan] * (len(columns) - len(row)))
        rows.append(row)

    df = pd.DataFrame(rows, columns=columns)
    return load_marker_dataframe(
        df,
        time_column="Time",
        marker_names=marker_names,
        units="m" if "mm" not in lines[2].lower() else "mm",
        name=name or path.stem,
        source_path=path,
        metadata=metadata,
    )


def load_marker_dataframe(
    df: pd.DataFrame,
    *,
    time_column: str = "time",
    marker_names: list[str] | None = None,
    units: str = "m",
    name: str | None = None,
    source_path: str | Path | None = None,
    metadata: dict | None = None,
):
    if marker_names is None:
        marker_names = []
        for col in df.columns:
            if col.endswith("_x") and f"{col[:-2]}_y" in df.columns and f"{col[:-2]}_z" in df.columns:
                marker_names.append(col[:-2])
    if not marker_names:
        raise ValueError("Could not infer marker names from DataFrame columns.")
    tcol = time_column
    if tcol not in df.columns:
        tcol = _coerce_time_column(df)
    time = pd.to_numeric(df[tcol], errors="coerce").to_numpy(dtype=float)
    frames = len(df)
    data = np.full((frames, len(marker_names), 3), np.nan, dtype=float)
    for m, marker in enumerate(marker_names):
        data[:, m, 0] = pd.to_numeric(df[f"{marker}_x"], errors="coerce").to_numpy(dtype=float)
        data[:, m, 1] = pd.to_numeric(df[f"{marker}_y"], errors="coerce").to_numpy(dtype=float)
        data[:, m, 2] = pd.to_numeric(df[f"{marker}_z"], errors="coerce").to_numpy(dtype=float)
    fps = 1.0 / np.nanmedian(np.diff(time)) if len(time) > 1 and np.nanmedian(np.diff(time)) > 0 else np.nan
    from ..core.trials import MarkerTrial

    from ..results import MarkerResult

    result = MarkerResult(
        name=name or "markers",
        data=data,
        time=time,
        landmark_names=marker_names,
        dims=("x", "y", "z"),
        confidence=None,
        metadata={"units": units, **(metadata or {})},
        source="trc" if source_path else "dataframe",
        fps=float(fps) if np.isfinite(fps) else None,
    )
    return MarkerTrial(name=name or "markers", markers=result, metadata=metadata or {}, source_path=source_path)


def write_trc(
    path: str | Path,
    *,
    time: np.ndarray,
    data: np.ndarray,
    marker_names: list[str],
    units: str = "m",
    fps: float | None = None,
):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fps is None:
        fps = 1.0 / np.nanmedian(np.diff(time)) if len(time) > 1 and np.nanmedian(np.diff(time)) > 0 else 30.0
    frames = data.shape[0]
    markers = data.shape[1]

    lines: list[str] = []
    lines.append(f"PathFileType\t4\t(X/Y/Z)\t{path.name}")
    lines.append("DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\tOrigDataRate\tOrigDataStartFrame\tOrigNumFrames")
    lines.append(f"{fps:.6f}\t{fps:.6f}\t{frames}\t{markers}\t{units}\t{fps:.6f}\t1\t{frames}")
    header_names = ["Frame#", "Time"]
    for marker in marker_names:
        header_names.extend([marker, "", ""])
    lines.append("\t".join(header_names))
    coord_labels = ["", ""]
    for idx in range(markers):
        coord_labels.extend([f"X{idx+1}", f"Y{idx+1}", f"Z{idx+1}"])
    lines.append("\t".join(coord_labels))
    scale = 1000.0 if units.lower() == "mm" else 1.0
    for i in range(frames):
        row = [str(i + 1), f"{float(time[i]):.6f}"]
        for m in range(markers):
            xyz = data[i, m, :] * scale
            row.extend([f"{float(xyz[0]):.6f}", f"{float(xyz[1]):.6f}", f"{float(xyz[2]):.6f}"])
        lines.append("\t".join(row))
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
