from __future__ import annotations

from typing import Sequence

import matplotlib.pyplot as plt
import pandas as pd


def plot_dataframe_columns(
    *,
    df: pd.DataFrame,
    columns: Sequence[str],
    time_column: str = "time",
    title: str | None = None,
    ylabel: str | None = None,
    figsize: tuple[float, float] = (10, 4),
    ax=None,
):
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Columns not found in DataFrame: {missing}")

    if time_column not in df.columns:
        raise ValueError(f"Time column '{time_column}' not found in DataFrame.")

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    for col in columns:
        ax.plot(df[time_column], df[col], label=col)

    ax.set_xlabel(time_column)
    if ylabel:
        ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig, ax