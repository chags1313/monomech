from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_storage(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    header_end = 0
    for i, line in enumerate(lines):
        if line.strip().lower() == "endheader":
            header_end = i
            break
    table = "\n".join(lines[header_end + 1 :])
    from io import StringIO
    return pd.read_csv(StringIO(table), sep=r"\s+|\t+", engine="python")


def storage_time_range(path: str | Path) -> tuple[float, float]:
    df = read_storage(path)
    time_col = "time" if "time" in df.columns else df.columns[0]
    return float(df[time_col].iloc[0]), float(df[time_col].iloc[-1])
