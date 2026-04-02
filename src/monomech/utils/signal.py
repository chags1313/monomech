"""NaN-aware signal helpers."""

from __future__ import annotations

import numpy as np


def fill_gaps_linear(values: np.ndarray | list[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=float).copy()
    if arr.size == 0:
        return arr
    mask = np.isfinite(arr)
    if mask.all():
        return arr
    if not mask.any():
        return np.zeros_like(arr)
    idx = np.arange(arr.size)
    arr[~mask] = np.interp(idx[~mask], idx[mask], arr[mask])
    return arr


def moving_average(values: np.ndarray | list[float], window: int) -> np.ndarray:
    arr = fill_gaps_linear(values)
    window = max(int(window), 1)
    if window == 1 or arr.size == 0:
        return arr
    if window == 2:
        left = arr
        right = np.roll(arr, -1)
        right[-1] = arr[-1]
        return 0.5 * (left + right)
    radius = window // 2
    padded = np.pad(arr, (radius, radius), mode="edge")
    kernel = np.ones(window, dtype=float) / window
    out = np.convolve(padded, kernel, mode="valid")
    return out[: arr.size]


def nanmedian_filter(values: np.ndarray | list[float], window: int) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    window = max(int(window), 1)
    if window == 1 or arr.size == 0:
        return arr.copy()
    radius = window // 2
    out = np.empty_like(arr)
    for i in range(arr.size):
        lo = max(0, i - radius)
        hi = min(arr.size, i + radius + 1)
        out[i] = np.nanmedian(arr[lo:hi])
    return out
