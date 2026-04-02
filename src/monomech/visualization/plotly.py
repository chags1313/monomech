"""Plotly figures for notebook and HTML export."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from ..constants import LANDMARK_INDEX, LANDMARK_NAMES, POSE_CONNECTIONS
from ..kinematics.metrics import compute_default_angle_traces
from ..types import TrialResult


def _frame_lines(xyz: np.ndarray):
    xs, ys, zs = [], [], []
    for a, b in POSE_CONNECTIONS:
        pa, pb = xyz[a], xyz[b]
        xs.extend([pa[0], pb[0], None])
        ys.extend([pa[1], pb[1], None])
        zs.extend([pa[2], pb[2], None])
    return xs, ys, zs


def make_pose_3d_figure(trial: TrialResult, coordinate_set: str = "global") -> go.Figure:
    pose = trial.get_pose(coordinate_set)
    xyz = pose.xyz
    first = xyz[0]
    line_x, line_y, line_z = _frame_lines(first)
    fig = go.Figure(
        data=[
            go.Scatter3d(x=line_x, y=line_y, z=line_z, mode="lines", name="skeleton"),
            go.Scatter3d(x=first[:, 0], y=first[:, 1], z=first[:, 2], mode="markers", name="joints", text=LANDMARK_NAMES),
        ]
    )

    frames = []
    for idx in range(pose.n_frames):
        frame_xyz = xyz[idx]
        line_x, line_y, line_z = _frame_lines(frame_xyz)
        frames.append(
            go.Frame(
                data=[
                    go.Scatter3d(x=line_x, y=line_y, z=line_z, mode="lines"),
                    go.Scatter3d(x=frame_xyz[:, 0], y=frame_xyz[:, 1], z=frame_xyz[:, 2], mode="markers", text=LANDMARK_NAMES),
                ],
                name=str(idx),
            )
        )
    fig.frames = frames
    fig.update_layout(
        title=f"3D pose ({coordinate_set})",
        template="plotly_dark",
        scene=dict(
            xaxis_title="X",
            yaxis_title="Y",
            zaxis_title="Z",
            aspectmode="data",
        ),
        updatemenus=[{
            "type": "buttons",
            "buttons": [
                {"label": "Play", "method": "animate", "args": [None, {"frame": {"duration": 30, "redraw": True}, "fromcurrent": True}]},
                {"label": "Pause", "method": "animate", "args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}]},
            ],
        }],
        sliders=[{
            "steps": [
                {"label": str(i), "method": "animate", "args": [[str(i)], {"mode": "immediate", "frame": {"duration": 0, "redraw": True}}]}
                for i in range(pose.n_frames)
            ]
        }],
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def make_pose_2d_figure(trial: TrialResult) -> go.Figure:
    if trial.pose2d is None:
        raise ValueError("pose2d is not available on this trial.")
    pose = trial.pose2d
    first = pose.xy[0]
    line_x, line_y = [], []
    for a, b in POSE_CONNECTIONS:
        pa, pb = first[a], first[b]
        line_x.extend([pa[0], pb[0], None])
        line_y.extend([pa[1], pb[1], None])
    fig = go.Figure(
        data=[
            go.Scatter(x=line_x, y=line_y, mode="lines", name="skeleton"),
            go.Scatter(x=first[:, 0], y=first[:, 1], mode="markers", name="joints", text=LANDMARK_NAMES),
        ]
    )
    frames = []
    for idx in range(pose.n_frames):
        frame_xy = pose.xy[idx]
        line_x, line_y = [], []
        for a, b in POSE_CONNECTIONS:
            pa, pb = frame_xy[a], frame_xy[b]
            line_x.extend([pa[0], pb[0], None])
            line_y.extend([pa[1], pb[1], None])
        frames.append(go.Frame(data=[go.Scatter(x=line_x, y=line_y, mode="lines"), go.Scatter(x=frame_xy[:, 0], y=frame_xy[:, 1], mode="markers", text=LANDMARK_NAMES)], name=str(idx)))
    fig.frames = frames
    fig.update_layout(
        title="2D pose",
        template="plotly_white",
        yaxis=dict(autorange="reversed", scaleanchor="x", scaleratio=1),
        xaxis_title="Normalized X",
        yaxis_title="Normalized Y",
        updatemenus=[{
            "type": "buttons",
            "buttons": [
                {"label": "Play", "method": "animate", "args": [None, {"frame": {"duration": 30, "redraw": True}, "fromcurrent": True}]},
                {"label": "Pause", "method": "animate", "args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}]},
            ]
        }],
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def make_joint_trace_figure(trial: TrialResult, coordinate_set: str = "global", landmark: str = "right_ankle") -> go.Figure:
    pose = trial.get_pose(coordinate_set)
    idx = LANDMARK_INDEX[landmark]
    xyz = pose.xyz[:, idx, :]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pose.time_s, y=xyz[:, 0], mode="lines", name="X"))
    fig.add_trace(go.Scatter(x=pose.time_s, y=xyz[:, 1], mode="lines", name="Y"))
    fig.add_trace(go.Scatter(x=pose.time_s, y=xyz[:, 2], mode="lines", name="Z"))
    angle_df = compute_default_angle_traces(pose)
    for col in [c for c in angle_df.columns if c != "time"][:2]:
        fig.add_trace(go.Scatter(x=angle_df["time"], y=angle_df[col], mode="lines", name=col, yaxis="y2"))
    fig.update_layout(
        title=f"Trajectories and angles for {landmark}",
        template="plotly_white",
        xaxis_title="Time (s)",
        yaxis=dict(title="Position"),
        yaxis2=dict(title="Angle (deg)", overlaying="y", side="right"),
        legend=dict(orientation="h"),
        margin=dict(l=40, r=40, t=50, b=40),
    )
    return fig
