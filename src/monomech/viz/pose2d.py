from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np

from .common import get_video_frame


def plot_pose2d_frame(
    *,
    image: np.ndarray,
    landmarks_xy: np.ndarray,
    confidence: np.ndarray | None = None,
    connections: Sequence[tuple[int, int]] = (),
    landmark_names: Sequence[str] | None = None,
    show_connections: bool = True,
    show_labels: bool = False,
    color_by_confidence: bool = False,
    confidence_min: float | None = None,
    point_size: float = 28.0,
    line_width: float = 1.75,
    figsize: tuple[float, float] = (8, 6),
    ax=None,
):
    pts = np.asarray(landmarks_xy, dtype=float)

    if pts.ndim != 2 or pts.shape[1] < 2:
        raise ValueError(f"Expected 2D landmarks of shape (n, 2), got {pts.shape}")

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    ax.imshow(image)
    ax.axis("off")

    h, w = image.shape[:2]
    xs = pts[:, 0] * w
    ys = pts[:, 1] * h

    valid = np.isfinite(xs) & np.isfinite(ys)

    if confidence is not None:
        conf = np.asarray(confidence, dtype=float)
        if conf.shape[0] != pts.shape[0]:
            raise ValueError("confidence length must match number of landmarks")
        if confidence_min is not None:
            valid = valid & np.isfinite(conf) & (conf >= confidence_min)

        if color_by_confidence:
            scatter = ax.scatter(xs[valid], ys[valid], s=point_size, c=conf[valid], cmap="viridis")
            fig.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04, label="confidence")
        else:
            ax.scatter(xs[valid], ys[valid], s=point_size)
    else:
        ax.scatter(xs[valid], ys[valid], s=point_size)

    if show_connections:
        for i, j in connections:
            if i < len(xs) and j < len(xs) and valid[i] and valid[j]:
                ax.plot([xs[i], xs[j]], [ys[i], ys[j]], linewidth=line_width)

    if show_labels and landmark_names is not None:
        for idx in np.where(valid)[0]:
            ax.text(xs[idx], ys[idx], str(landmark_names[idx]), fontsize=8)

    return fig, ax


def plot_pose2d_frames(
    *,
    video_path: str | Path,
    pose_xy: np.ndarray,
    frames: Sequence[int],
    confidence: np.ndarray | None = None,
    connections: Sequence[tuple[int, int]] = (),
    landmark_names: Sequence[str] | None = None,
    show_connections: bool = True,
    show_labels: bool = False,
    color_by_confidence: bool = False,
    confidence_min: float | None = None,
    ncols: int = 2,
    figsize_per_panel: tuple[float, float] = (6, 4),
):
    frames = list(frames)
    n = len(frames)
    ncols = max(1, int(ncols))
    nrows = int(np.ceil(n / ncols))

    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(figsize_per_panel[0] * ncols, figsize_per_panel[1] * nrows),
        squeeze=False,
    )
    axes = axes.ravel()

    for ax, frame_idx in zip(axes, frames):
        image = get_video_frame(video_path, frame_idx)
        conf = None if confidence is None else confidence[frame_idx]
        plot_pose2d_frame(
            image=image,
            landmarks_xy=pose_xy[frame_idx],
            confidence=conf,
            connections=connections,
            landmark_names=landmark_names,
            show_connections=show_connections,
            show_labels=show_labels,
            color_by_confidence=color_by_confidence,
            confidence_min=confidence_min,
            ax=ax,
        )
        ax.set_title(f"frame {frame_idx}")

    for ax in axes[n:]:
        ax.axis("off")

    fig.tight_layout()
    return fig, axes