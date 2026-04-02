"""MediaPipe Tasks backend."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..config import MediaPipePoseConfig
from ..constants import LANDMARK_NAMES
from ..exceptions import ProcessingError
from ..io.video import iter_video_frames, open_video_metadata
from ..types import PoseSequence2D, PoseSequence3D, TrialResult
from ..utils.optional import import_optional
from .model_zoo import resolve_pose_model_asset


@dataclass(slots=True)
class MediaPipePoseEstimator:
    config: MediaPipePoseConfig

    def _create_landmarker(self):
        mp = import_optional("mediapipe", extra_name="mediapipe")
        model_path = resolve_pose_model_asset(
            self.config.model_asset_path,
            model_variant=self.config.model_variant,
            allow_download=self.config.allow_model_download,
            cache_dir=self.config.model_cache_dir,
        )
        BaseOptions = mp.tasks.BaseOptions
        PoseLandmarker = mp.tasks.vision.PoseLandmarker
        PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
        RunningMode = mp.tasks.vision.RunningMode
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=RunningMode.VIDEO,
            num_poses=self.config.num_poses,
            min_pose_detection_confidence=self.config.min_pose_detection_confidence,
            min_pose_presence_confidence=self.config.min_pose_presence_confidence,
            min_tracking_confidence=self.config.min_tracking_confidence,
            output_segmentation_masks=self.config.output_segmentation_masks,
        )
        return mp, PoseLandmarker.create_from_options(options)

    def process_video(self, video_path: str | Path) -> TrialResult:
        meta = open_video_metadata(video_path)
        mp, landmarker = self._create_landmarker()

        xy_frames: list[np.ndarray] = []
        world_frames: list[np.ndarray] = []
        vis_frames: list[np.ndarray] = []
        time_s: list[float] = []

        try:
            for frame in iter_video_frames(meta.path, target_fps=self.config.target_fps, stride=self.config.stride):
                rgb = cv2.cvtColor(frame.bgr, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = landmarker.detect_for_video(mp_image, int(round(frame.time_s * 1000.0)))

                xy = np.full((len(LANDMARK_NAMES), 2), np.nan, dtype=float)
                xyz = np.full((len(LANDMARK_NAMES), 3), np.nan, dtype=float)
                vis = np.zeros((len(LANDMARK_NAMES),), dtype=float)

                if getattr(result, "pose_landmarks", None):
                    lms = result.pose_landmarks[0]
                    for idx, lm in enumerate(lms[: len(LANDMARK_NAMES)]):
                        xy[idx, 0] = float(lm.x)
                        xy[idx, 1] = float(lm.y)
                        vis[idx] = float(getattr(lm, "visibility", np.nan))

                if getattr(result, "pose_world_landmarks", None):
                    wlms = result.pose_world_landmarks[0]
                    for idx, lm in enumerate(wlms[: len(LANDMARK_NAMES)]):
                        xyz[idx, 0] = float(lm.x)
                        xyz[idx, 1] = float(lm.y)
                        xyz[idx, 2] = float(lm.z)
                        if not np.isfinite(vis[idx]):
                            vis[idx] = float(getattr(lm, "visibility", np.nan))

                xy_frames.append(xy)
                world_frames.append(xyz)
                vis_frames.append(vis)
                time_s.append(frame.time_s)
        except Exception as exc:
            raise ProcessingError(f"MediaPipe processing failed for {video_path}: {exc}") from exc
        finally:
            landmarker.close()

        if not xy_frames:
            raise ProcessingError(f"No frames were processed for {video_path}")

        pose2d = PoseSequence2D(
            time_s=np.asarray(time_s, dtype=float),
            xy=np.stack(xy_frames, axis=0),
            visibility=np.stack(vis_frames, axis=0),
            metadata={"video_path": str(meta.path), "fps": meta.fps, "width": meta.width, "height": meta.height},
        )
        world_pose = PoseSequence3D(
            time_s=np.asarray(time_s, dtype=float),
            xyz=np.stack(world_frames, axis=0),
            visibility=np.stack(vis_frames, axis=0),
            metadata={"video_path": str(meta.path), "fps": meta.fps, "width": meta.width, "height": meta.height},
        )
        return TrialResult(
            name=meta.path.stem,
            video_path=meta.path,
            fps=meta.fps,
            pose2d=pose2d,
            world_pose=world_pose,
            metadata={"width": meta.width, "height": meta.height, "duration_s": meta.duration_s},
        )
