"""3D math helpers."""

from __future__ import annotations

import math

import numpy as np


def midpoint(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return 0.5 * (a + b)


def safe_norm(v: np.ndarray, axis: int = -1, keepdims: bool = False) -> np.ndarray:
    return np.linalg.norm(v, axis=axis, keepdims=keepdims)


def unit_vector(v: np.ndarray, axis: int = -1) -> np.ndarray:
    n = safe_norm(v, axis=axis, keepdims=True)
    n = np.where(n < 1e-12, 1.0, n)
    return v / n


def angle_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    ba = a - b
    bc = c - b
    nba = np.linalg.norm(ba)
    nbc = np.linalg.norm(bc)
    if nba < 1e-12 or nbc < 1e-12:
        return float("nan")
    cosang = float(np.dot(ba, bc) / (nba * nbc))
    cosang = max(-1.0, min(1.0, cosang))
    return math.degrees(math.acos(cosang))
