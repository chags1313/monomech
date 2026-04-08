from __future__ import annotations

from pathlib import Path

from .common import get_connections, resolve_video_path
from .pose2d import plot_pose2d_frame, plot_pose2d_frames
from .pose3d import plot_pose3d_frame, plot_pose3d_frames
from .timeseries import plot_dataframe_columns


def _pose2d_plot_frame(
    self,
    frame: int,
    *,
    video_path: str | Path | None = None,
    show_connections: bool = True,
    show_labels: bool = False,
    color_by_confidence: bool = False,
    confidence_min: float | None = None,
):
    from .common import get_video_frame

    vp = resolve_video_path(self, video_path)
    image = get_video_frame(vp, frame)

    return plot_pose2d_frame(
        image=image,
        landmarks_xy=self.data[frame],
        confidence=self.confidence[frame] if self.confidence is not None else None,
        connections=get_connections(self.landmark_names),
        landmark_names=self.landmark_names,
        show_connections=show_connections,
        show_labels=show_labels,
        color_by_confidence=color_by_confidence,
        confidence_min=confidence_min,
    )


def _pose2d_plot_frames(
    self,
    frames,
    *,
    video_path: str | Path | None = None,
    show_connections: bool = True,
    show_labels: bool = False,
    color_by_confidence: bool = False,
    confidence_min: float | None = None,
    ncols: int = 2,
):
    vp = resolve_video_path(self, video_path)
    return plot_pose2d_frames(
        video_path=vp,
        pose_xy=self.data,
        frames=frames,
        confidence=self.confidence,
        connections=get_connections(self.landmark_names),
        landmark_names=self.landmark_names,
        show_connections=show_connections,
        show_labels=show_labels,
        color_by_confidence=color_by_confidence,
        confidence_min=confidence_min,
        ncols=ncols,
    )


def _pose3d_plot_frame(
    self,
    frame: int,
    *,
    show_connections: bool = True,
    show_floor: bool = False,
    show_axes: bool = True,
    show_labels: bool = False,
    elev: float = 20.0,
    azim: float = 110.0,
):
    return plot_pose3d_frame(
        landmarks_xyz=self.data[frame],
        connections=get_connections(self.landmark_names),
        landmark_names=self.landmark_names,
        show_connections=show_connections,
        show_floor=show_floor,
        show_axes=show_axes,
        show_labels=show_labels,
        elev=elev,
        azim=azim,
    )


def _pose3d_plot_frames(
    self,
    frames,
    *,
    show_connections: bool = True,
    show_floor: bool = False,
    show_axes: bool = True,
    show_labels: bool = False,
    elev: float = 20.0,
    azim: float = 110.0,
    ncols: int = 2,
):
    return plot_pose3d_frames(
        pose_xyz=self.data,
        frames=frames,
        connections=get_connections(self.landmark_names),
        landmark_names=self.landmark_names,
        show_connections=show_connections,
        show_floor=show_floor,
        show_axes=show_axes,
        show_labels=show_labels,
        elev=elev,
        azim=azim,
        ncols=ncols,
    )


def _marker_plot_frame(
    self,
    frame: int,
    *,
    show_connections: bool = False,
    show_floor: bool = False,
    show_axes: bool = True,
    show_labels: bool = True,
    elev: float = 20.0,
    azim: float = 110.0,
):
    return plot_pose3d_frame(
        landmarks_xyz=self.data[frame],
        connections=get_connections(self.landmark_names) if show_connections else [],
        landmark_names=self.landmark_names,
        show_connections=show_connections,
        show_floor=show_floor,
        show_axes=show_axes,
        show_labels=show_labels,
        elev=elev,
        azim=azim,
    )


def _marker_plot_frames(
    self,
    frames,
    *,
    show_connections: bool = False,
    show_floor: bool = False,
    show_axes: bool = True,
    show_labels: bool = True,
    elev: float = 20.0,
    azim: float = 110.0,
    ncols: int = 2,
):
    return plot_pose3d_frames(
        pose_xyz=self.data,
        frames=frames,
        connections=get_connections(self.landmark_names) if show_connections else [],
        landmark_names=self.landmark_names,
        show_connections=show_connections,
        show_floor=show_floor,
        show_axes=show_axes,
        show_labels=show_labels,
        elev=elev,
        azim=azim,
        ncols=ncols,
    )


def _storage_plot_coordinate(self, column: str):
    df = self.to_dataframe()
    return plot_dataframe_columns(
        df=df,
        columns=[column],
        time_column="time",
        title=f"{column}",
        ylabel="value",
    )


def _storage_plot_coordinates(self, columns):
    df = self.to_dataframe()
    return plot_dataframe_columns(
        df=df,
        columns=columns,
        time_column="time",
        title="OpenSim coordinates",
        ylabel="value",
    )


def _storage_plot_columns(self, columns):
    df = self.to_dataframe()
    return plot_dataframe_columns(
        df=df,
        columns=columns,
        time_column="time",
        title="OpenSim results",
        ylabel="value",
    )


def _storage_plot_forces(self, columns):
    df = self.to_dataframe()
    return plot_dataframe_columns(
        df=df,
        columns=columns,
        time_column="time",
        title="Forces",
        ylabel="force",
    )


def _storage_plot_moments(self, columns):
    df = self.to_dataframe()
    return plot_dataframe_columns(
        df=df,
        columns=columns,
        time_column="time",
        title="Moments",
        ylabel="moment",
    )


def install_plot_methods() -> None:
    from ..results import (
        MarkerResult,
        Pose2DResult,
        Pose3DGlobalResult,
        Pose3DWorldResult,
        StorageResult,
    )

    Pose2DResult.plot_frame = _pose2d_plot_frame
    Pose2DResult.plot_frames = _pose2d_plot_frames

    Pose3DWorldResult.plot_frame = _pose3d_plot_frame
    Pose3DWorldResult.plot_frames = _pose3d_plot_frames

    Pose3DGlobalResult.plot_frame = _pose3d_plot_frame
    Pose3DGlobalResult.plot_frames = _pose3d_plot_frames

    MarkerResult.plot_frame = _marker_plot_frame
    MarkerResult.plot_frames = _marker_plot_frames

    StorageResult.plot_coordinate = _storage_plot_coordinate
    StorageResult.plot_coordinates = _storage_plot_coordinates
    StorageResult.plot_columns = _storage_plot_columns
    StorageResult.plot_forces = _storage_plot_forces
    StorageResult.plot_moments = _storage_plot_moments