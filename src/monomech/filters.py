from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
from scipy.interpolate import CubicSpline, PchipInterpolator
from scipy.signal import butter, filtfilt, medfilt, savgol_filter

from .landmarks import NAME_TO_INDEX, SEGMENTS


def _nan_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    in_run = False
    start = 0
    for i, val in enumerate(mask):
        if val and not in_run:
            start = i
            in_run = True
        elif not val and in_run:
            runs.append((start, i))
            in_run = False
    if in_run:
        runs.append((start, len(mask)))
    return runs


def interpolate_nan_1d(
    y: np.ndarray,
    *,
    method: str = "pchip",
    max_gap_frames: int = 10,
    fill_edges: bool = False,
) -> np.ndarray:
    out = np.asarray(y, dtype=float).copy()
    x = np.arange(len(out), dtype=float)
    missing = ~np.isfinite(out)
    if not missing.any():
        return out

    valid = np.isfinite(out)
    if valid.sum() < 2:
        return out

    for start, stop in _nan_runs(missing):
        gap = stop - start
        if gap > max_gap_frames:
            continue
        if not fill_edges and (start == 0 or stop == len(out)):
            continue
        left = max(0, start - 1)
        right = min(len(out), stop)
        known = np.isfinite(out)
        if known.sum() < 2:
            continue
        xv = x[known]
        yv = out[known]
        xs = x[start:stop]
        try:
            if method == "linear" or len(xv) < 3:
                out[start:stop] = np.interp(xs, xv, yv)
            elif method == "nearest_valid":
                for idx in range(start, stop):
                    left_i = max(i for i in range(0, idx + 1) if np.isfinite(out[i])) if np.isfinite(out[: idx + 1]).any() else None
                    right_candidates = np.where(np.isfinite(out[idx:]))[0]
                    right_i = int(idx + right_candidates[0]) if len(right_candidates) else None
                    if left_i is None and right_i is None:
                        continue
                    if left_i is None:
                        out[idx] = out[right_i]
                    elif right_i is None:
                        out[idx] = out[left_i]
                    else:
                        out[idx] = out[left_i] if idx - left_i <= right_i - idx else out[right_i]
            elif method == "cubic_spline":
                out[start:stop] = CubicSpline(xv, yv)(xs)
            else:
                out[start:stop] = PchipInterpolator(xv, yv)(xs)
        except Exception:
            out[start:stop] = np.interp(xs, xv, yv)
    return out


def gap_fill_array(
    data: np.ndarray,
    *,
    method: str = "pchip",
    max_gap_frames: int = 10,
    fill_edges: bool = False,
) -> np.ndarray:
    out = np.asarray(data, dtype=float).copy()
    frames, markers, dims = out.shape
    for m in range(markers):
        for d in range(dims):
            out[:, m, d] = interpolate_nan_1d(
                out[:, m, d],
                method=method if method not in {"rigid_segment", "rigid_cluster"} else "pchip",
                max_gap_frames=max_gap_frames,
                fill_edges=fill_edges,
            )
    return out


def _safe_cutoff(cutoff_hz: float, fps: float) -> float:
    nyq = fps / 2.0
    return min(max(cutoff_hz, 1e-3), nyq * 0.99)


def butterworth_array(data: np.ndarray, fps: float, cutoff_hz: float = 6.0, order: int = 4) -> np.ndarray:
    arr = np.asarray(data, dtype=float).copy()
    if fps <= 0 or arr.shape[0] < max(5, order * 3):
        return arr
    wn = _safe_cutoff(cutoff_hz, fps) / (fps / 2.0)
    b, a = butter(order, wn, btype="low")
    for m in range(arr.shape[1]):
        for d in range(arr.shape[2]):
            y = arr[:, m, d]
            valid = np.isfinite(y)
            if valid.sum() < max(order + 2, 6):
                continue
            filled = interpolate_nan_1d(y, method="linear", max_gap_frames=len(y), fill_edges=True)
            try:
                arr[:, m, d] = filtfilt(b, a, filled)
            except Exception:
                arr[:, m, d] = filled
    return arr


def savgol_array(data: np.ndarray, window_length: int = 11, polyorder: int = 3) -> np.ndarray:
    arr = np.asarray(data, dtype=float).copy()
    n = arr.shape[0]
    if n < 5:
        return arr
    window_length = min(window_length if window_length % 2 == 1 else window_length + 1, n if n % 2 == 1 else n - 1)
    window_length = max(window_length, polyorder + 2 + ((polyorder + 2) % 2 == 0))
    for m in range(arr.shape[1]):
        for d in range(arr.shape[2]):
            y = arr[:, m, d]
            valid = np.isfinite(y)
            if valid.sum() < window_length:
                continue
            filled = interpolate_nan_1d(y, method="linear", max_gap_frames=len(y), fill_edges=True)
            arr[:, m, d] = savgol_filter(filled, window_length=window_length, polyorder=min(polyorder, window_length - 2))
    return arr


def median_array(data: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    arr = np.asarray(data, dtype=float).copy()
    kernel_size = kernel_size if kernel_size % 2 == 1 else kernel_size + 1
    for m in range(arr.shape[1]):
        for d in range(arr.shape[2]):
            y = arr[:, m, d]
            valid = np.isfinite(y)
            if valid.sum() < kernel_size:
                continue
            filled = interpolate_nan_1d(y, method="linear", max_gap_frames=len(y), fill_edges=True)
            arr[:, m, d] = medfilt(filled, kernel_size=kernel_size)
    return arr


def confidence_weighted_smooth(
    data: np.ndarray,
    confidence: np.ndarray | None,
    *,
    alpha_high: float = 0.75,
    alpha_low: float = 0.15,
) -> np.ndarray:
    arr = np.asarray(data, dtype=float).copy()
    conf = None if confidence is None else np.asarray(confidence, dtype=float)
    for m in range(arr.shape[1]):
        for d in range(arr.shape[2]):
            y = interpolate_nan_1d(arr[:, m, d], method="linear", max_gap_frames=len(arr), fill_edges=True)
            prev = y[0]
            for i in range(1, len(y)):
                c = 1.0 if conf is None else float(np.nan_to_num(conf[i, m], nan=0.0))
                alpha = alpha_low + (alpha_high - alpha_low) * max(0.0, min(1.0, c))
                prev = alpha * y[i] + (1.0 - alpha) * prev
                arr[i, m, d] = prev
            arr[0, m, d] = y[0]
    return arr


def preserve_segment_lengths(data: np.ndarray, landmark_names: list[str]) -> np.ndarray:
    arr = np.asarray(data, dtype=float).copy()
    index = {name: i for i, name in enumerate(landmark_names)}
    reference_lengths: dict[str, float] = {}
    for segment_name, (a_name, b_name) in SEGMENTS.items():
        if a_name not in index or b_name not in index:
            continue
        a = arr[:, index[a_name], :]
        b = arr[:, index[b_name], :]
        dist = np.linalg.norm(a - b, axis=1)
        valid = np.isfinite(dist)
        if valid.any():
            reference_lengths[segment_name] = float(np.nanmedian(dist[valid]))
    if not reference_lengths:
        return arr

    for segment_name, (a_name, b_name) in SEGMENTS.items():
        if segment_name not in reference_lengths or a_name not in index or b_name not in index:
            continue
        target = reference_lengths[segment_name]
        ai = index[a_name]
        bi = index[b_name]
        for f in range(arr.shape[0]):
            pa = arr[f, ai, :]
            pb = arr[f, bi, :]
            if not np.all(np.isfinite(pa)) or not np.all(np.isfinite(pb)):
                continue
            vec = pb - pa
            norm = np.linalg.norm(vec)
            if norm < 1e-12:
                continue
            arr[f, bi, :] = pa + (vec / norm) * target
    return arr


def apply_smoothing(
    data: np.ndarray,
    *,
    method: str = "butterworth",
    fps: float = 30.0,
    confidence: np.ndarray | None = None,
    cutoff_hz: float = 6.0,
    order: int = 4,
    window_length: int = 11,
    polyorder: int = 3,
    preserve_lengths: bool = False,
    landmark_names: list[str] | None = None,
) -> np.ndarray:
    method = method.lower()
    if method == "none":
        out = np.asarray(data, dtype=float).copy()
    elif method == "butterworth":
        out = butterworth_array(data, fps=fps, cutoff_hz=cutoff_hz, order=order)
    elif method == "savgol":
        out = savgol_array(data, window_length=window_length, polyorder=polyorder)
    elif method == "median":
        out = median_array(data, kernel_size=window_length)
    elif method in {"kalman_confidence", "confidence", "confidence_weighted"}:
        out = confidence_weighted_smooth(data, confidence)
    else:
        raise ValueError(f"Unsupported smoothing method: {method}")
    if preserve_lengths and landmark_names is not None:
        out = preserve_segment_lengths(out, landmark_names)
    return out
