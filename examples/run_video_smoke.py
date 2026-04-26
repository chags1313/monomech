from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a monomech video smoke test.")
    parser.add_argument("video", type=Path, help="Path to an MP4 or other OpenCV-readable video.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/video_smoke"))
    parser.add_argument("--stride", type=int, default=30, help="Frame stride for pose estimation.")
    parser.add_argument("--opensim", action="store_true", help="Also run OpenSim scale, IK, and ID.")
    parser.add_argument("--body-mass-kg", type=float, default=75.0)
    args = parser.parse_args()

    import monomech as mm

    args.output_dir.mkdir(parents=True, exist_ok=True)

    trial = mm.load_video(args.video)
    pose2d = trial.estimate_pose2d(stride=args.stride)
    pose3d_world = trial.estimate_pose3d_world(smooth=False)
    pose3d_global = trial.estimate_pose3d_global(world_pose=pose3d_world, pose2d=pose2d)

    csv_path = pose3d_global.to_csv(args.output_dir / f"{trial.name}_global.csv")
    trc_path = pose3d_global.to_trc(args.output_dir / f"{trial.name}_global.trc")

    report: dict[str, object] = {
        "video": str(args.video),
        "metadata": trial.metadata,
        "pose2d_shape": list(pose2d.data.shape),
        "pose2d_finite_pct": float(np.isfinite(pose2d.data).mean() * 100.0),
        "pose2d_mean_confidence": float(np.nanmean(pose2d.confidence)),
        "pose3d_global_finite_pct": float(np.isfinite(pose3d_global.data).mean() * 100.0),
        "csv_path": str(csv_path),
        "trc_path": str(trc_path),
    }

    if args.opensim:
        model_path = mm.get_builtin_osim_model("pose")
        scale = trial.run_opensim_scale(
            model_path=model_path,
            trc_path=trc_path,
            output_dir=args.output_dir / "scale",
        )
        ik = trial.run_opensim_ik(
            model_path=scale.scaled_model_path,
            trc_path=trc_path,
            output_dir=args.output_dir / "ik",
        )
        loads = mm.external.estimate_grf(
            pose3d=pose3d_global,
            body_mass_kg=args.body_mass_kg,
        )
        id_result = trial.run_opensim_id(
            model_path=scale.scaled_model_path,
            ik_path=ik.path,
            external_forces=loads,
            output_dir=args.output_dir / "id",
        )
        report.update(
            {
                "scaled_model_path": str(scale.scaled_model_path),
                "ik_path": str(ik.path),
                "ik_marker_error_summary": ik.metadata.get("marker_error_summary") if ik.metadata else None,
                "id_path": str(id_result.path),
                "external_loads_xml_path": id_result.metadata.get("external_loads_xml_path")
                if id_result.metadata
                else None,
            }
        )

    report_path = args.output_dir / f"{trial.name}_smoke_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
