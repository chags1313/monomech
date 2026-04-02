"""Command line interface for the modular wrapper."""

from __future__ import annotations

import argparse

from .config import MediaPipePoseConfig, OpenSimConfig, PipelineConfig
from .workflow import FullPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="monomech")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the full modular pipeline")
    run.add_argument("--video", required=True, help="Path to the source video.")
    run.add_argument("--output-dir", required=True, help="Directory for exported tables and dashboard.")
    run.add_argument("--model", default=None, help="MediaPipe pose landmarker .task asset.")
    run.add_argument("--target-fps", type=float, default=60.0)
    run.add_argument("--opensim-model", default=None, help="Optional .osim model path.")
    run.add_argument("--run-ik", action="store_true")
    run.add_argument("--run-id", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        config = PipelineConfig(
            pose=MediaPipePoseConfig(model_asset_path=args.model, target_fps=args.target_fps),
            opensim=OpenSimConfig(model_path=args.opensim_model, run_ik=args.run_ik, run_id=args.run_id),
        )
        pipeline = FullPipeline(config=config)
        result = pipeline.run(args.video, output_dir=args.output_dir)
        print("Completed stages:", ", ".join(result.available_stages()))
        print("Artifacts:")
        for key, path in sorted(result.artifacts.items()):
            print(f"  {key}: {path}")
        return 0
    parser.error("Unknown command")
    return 2
