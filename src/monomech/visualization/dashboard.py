"""Self-contained notebook / HTML dashboard export."""

from __future__ import annotations

from pathlib import Path

from ..types import TrialResult
from ..utils.files import ensure_dir
from .plotly import make_joint_trace_figure, make_pose_2d_figure, make_pose_3d_figure


def build_trial_dashboard_html(trial: TrialResult, coordinate_set: str = "global", joint_for_trace: str = "right_ankle", include_plotlyjs: str | bool = "inline") -> str:
    fig3d = make_pose_3d_figure(trial, coordinate_set=coordinate_set)
    fig2d = make_pose_2d_figure(trial) if trial.pose2d is not None else None
    trace_fig = make_joint_trace_figure(trial, coordinate_set=coordinate_set, landmark=joint_for_trace)

    fig3d_html = fig3d.to_html(full_html=False, include_plotlyjs=include_plotlyjs)
    include_plotlyjs = False
    fig2d_html = fig2d.to_html(full_html=False, include_plotlyjs=include_plotlyjs) if fig2d is not None else ""
    trace_html = trace_fig.to_html(full_html=False, include_plotlyjs=False)

    info_items = [
        ("Trial", trial.name),
        ("FPS", f"{trial.fps:.3f}"),
        ("Video", str(trial.video_path) if trial.video_path else "(none)"),
        ("Coordinate set", coordinate_set),
        ("Artifacts", str(len(trial.artifacts))),
    ]
    info_html = "".join(f"<div class='card'><div class='label'>{k}</div><div class='value'>{v}</div></div>" for k, v in info_items)
    return f"""
<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{trial.name} dashboard</title>
<style>
body {{ font-family: Inter, system-ui, sans-serif; margin: 0; background: #0b1020; color: #eef2ff; }}
.wrapper {{ max-width: 1500px; margin: 0 auto; padding: 20px; }}
.grid {{ display: grid; grid-template-columns: repeat(12, 1fr); gap: 18px; }}
.panel {{ background: linear-gradient(180deg,#131a33,#0f1730); border: 1px solid #253259; border-radius: 18px; padding: 14px; box-shadow: 0 12px 30px rgba(0,0,0,.20); }}
.panel.wide {{ grid-column: span 12; }}
.panel.half {{ grid-column: span 6; }}
.metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 18px; }}
.card {{ background: rgba(255,255,255,.03); border: 1px solid #263054; border-radius: 14px; padding: 12px; }}
.label {{ font-size: 12px; color: #a9b5da; margin-bottom: 6px; }}
.value {{ font-size: 15px; font-weight: 600; word-break: break-word; }}
h1 {{ font-size: 24px; margin: 0 0 14px; }}
p {{ color: #c9d3f3; }}
@media (max-width: 980px) {{ .panel.half {{ grid-column: span 12; }} }}
</style>
</head>
<body>
<div class='wrapper'>
  <h1>{trial.name} — monomech dashboard</h1>
  <div class='metrics'>{info_html}</div>
  <div class='grid'>
    <section class='panel wide'>{fig3d_html}</section>
    <section class='panel half'>{fig2d_html}</section>
    <section class='panel half'>{trace_html}</section>
  </div>
</div>
</body>
</html>
"""


def export_trial_dashboard_html(trial: TrialResult, output_path: str | Path, coordinate_set: str = "global", joint_for_trace: str = "right_ankle") -> Path:
    path = Path(output_path)
    ensure_dir(path.parent)
    html = build_trial_dashboard_html(trial, coordinate_set=coordinate_set, joint_for_trace=joint_for_trace)
    path.write_text(html, encoding="utf-8")
    return path


def display_trial_dashboard(trial: TrialResult, coordinate_set: str = "global", joint_for_trace: str = "right_ankle"):
    from IPython.display import HTML
    return HTML(build_trial_dashboard_html(trial, coordinate_set=coordinate_set, joint_for_trace=joint_for_trace))
