"""Notebook convenience helpers."""

from __future__ import annotations

from IPython.display import HTML, display

from .visualization.dashboard import build_trial_dashboard_html, display_trial_dashboard


def display_stage_table(stage_result, table: str = "df", n: int = 10):
    df = stage_result.table(table).head(n)
    display(df)
    return df


def display_stage_summary(stage_result):
    df = stage_result.tables.get("summary", stage_result.df.head(0))
    display(df)
    return df


__all__ = [
    "build_trial_dashboard_html",
    "display_stage_summary",
    "display_stage_table",
    "display_trial_dashboard",
    "HTML",
]
