from __future__ import annotations

from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np

from .common import set_equal_3d_axes


def plot_pose3d_frame(
    *,
    landmarks_xyz: np.ndarray,
    connections: Sequence[tuple[int, int]] = (),
    landmark_names: Sequence[str] | None = None,
    show_connections: bool = True,
    show_floor: bool = False,
    show_axes: bool = True,
    show_labels: bool = False,
    elev: float = 20.0,
    azim: float = 110.0,
    point_size: float = 28.0,
    line_width: float = 1.75,
    figsize: tuple[float, float] = (7, 7),
    ax=None,
):
    pts = np.asarray(landmarks_xyz, dtype=float)

    if pts.ndim != 2 or pts.shape[1] < 3:
        raise ValueError(f"Expected 3D landmarks of shape (n, 3), got {pts.shape}")

    if ax is None:
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111, projection="3d")
    else:
        fig = ax.figure

    x = pts[:, 0]
    y = pts[:, 1]
    z = pts[:, 2]

    valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    ax.scatter(x[valid], y[valid], z[valid], s=point_size)

    if show_connections:
        for i, j in connections:
            if i < len(x) and j < len(x) and valid[i] and valid[j]:
                ax.plot([x[i], x[j]], [y[i], y[j]], [z[i], z[j]], linewidth=line_width)

    if show_labels and landmark_names is not None:
        for idx in np.where(valid)[0]:
            ax.text(x[idx], y[idx], z[idx], str(landmark_names[idx]), fontsize=8)

    if show_floor and np.any(valid):
        floor_y = float(np.nanmin(y[valid]))
        xr = np.array([np.nanmin(x[valid]), np.nanmax(x[valid])], dtype=float)
        zr = np.array([np.nanmin(z[valid]), np.nanmax(z[valid])], dtype=float)
        if np.isfinite(xr).all() and np.isfinite(zr).all():
            X, Z = np.meshgrid(xr, zr)
            Y = np.full_like(X, floor_y)
            ax.plot_surface(X, Y, Z, alpha=0.12)

    if show_axes:
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
    else:
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_zticks([])

    if np.any(valid):
        set_equal_3d_axes(ax, pts[valid])

    ax.view_init(elev=elev, azim=azim)
    return fig, ax


def plot_pose3d_frames(
    *,
    pose_xyz: np.ndarray,
    frames: Sequence[int],
    connections: Sequence[tuple[int, int]] = (),
    landmark_names: Sequence[str] | None = None,
    show_connections: bool = True,
    show_floor: bool = False,
    show_axes: bool = True,
    show_labels: bool = False,
    elev: float = 20.0,
    azim: float = 110.0,
    ncols: int = 2,
    figsize_per_panel: tuple[float, float] = (6, 5),
):
    frames = list(frames)
    n = len(frames)
    ncols = max(1, int(ncols))
    nrows = int(np.ceil(n / ncols))

    fig = plt.figure(figsize=(figsize_per_panel[0] * ncols, figsize_per_panel[1] * nrows))
    axes = []

    for idx, frame_idx in enumerate(frames, start=1):
        ax = fig.add_subplot(nrows, ncols, idx, projection="3d")
        axes.append(ax)
        plot_pose3d_frame(
            landmarks_xyz=pose_xyz[frame_idx],
            connections=connections,
            landmark_names=landmark_names,
            show_connections=show_connections,
            show_floor=show_floor,
            show_axes=show_axes,
            show_labels=show_labels,
            elev=elev,
            azim=azim,
            ax=ax,
        )
        ax.set_title(f"frame {frame_idx}")

    fig.tight_layout()
    return fig, axes