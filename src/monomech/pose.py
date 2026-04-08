from __future__ import annotations

from pathlib import Path

import imageio.v3 as iio
import numpy as np

from .config import Pose2DConfig, Pose3DGlobalConfig
from .landmarks import FOOT_MARKERS, JOINT_NAMES, NAME_TO_INDEX
from .resources import builtin_pose_model_path
from .results import Pose2DResult, Pose3DGlobalResult, Pose3DWorldResult


def _require_mediapipe():
    import mediapipe as mp
    return mp


def _read_video_meta(video_path: str | Path) -> dict:
    video_path = Path(video_path)

    try:
        import cv2  # type: ignore

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0) or None
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0) or None
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) or None
        cap.release()

        return {
            "fps": fps,
            "width": width,
            "height": height,
            "nframes": frame_count,
            "meta": {"backend": "opencv"},
        }
    except Exception as exc:
        raise RuntimeError(f"Failed to probe video with OpenCV: {video_path}") from exc


def _iter_video_frames(video_path: str | Path):
    import cv2  # type: ignore

    video_path = Path(video_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video for reading: {video_path}")

    frame_idx = 0
    yielded = 0
    try:
        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            yield frame_idx, frame_rgb
            yielded += 1
            frame_idx += 1
    finally:
        cap.release()

    if yielded == 0:
        raise RuntimeError(
            f"No frames could be read from video: {video_path}. "
            "This usually means the video backend could not decode the file."
        )


def _effective_stride(
    *,
    source_fps: float,
    requested_fps: float | None,
    stride: int,
) -> int:
    stride = max(1, int(stride))
    if requested_fps is None or requested_fps <= 0 or requested_fps >= source_fps:
        return stride

    fps_stride = max(1, int(round(source_fps / requested_fps)))
    return max(stride, fps_stride)


def _get_pose_model_path(config: Pose2DConfig) -> Path:
    pose_model_path = getattr(config, "pose_model_path", None)
    if pose_model_path is not None:
        path = Path(pose_model_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Pose model file not found: {path}")
        return path

    # Use packaged default model
    with builtin_pose_model_path() as model_path:
        return Path(model_path).resolve()


def estimate_pose_from_video(
    video_path: str | Path,
    *,
    config: Pose2DConfig | None = None,
) -> tuple[Pose2DResult, Pose3DWorldResult]:
    config = config or Pose2DConfig()
    video_path = Path(video_path).resolve()

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    mp = _require_mediapipe()
    meta = _read_video_meta(video_path)
    source_fps = float(meta["fps"])
    stride = _effective_stride(
        source_fps=source_fps,
        requested_fps=getattr(config, "sample_fps", None),
        stride=getattr(config, "stride", 1),
    )

    BaseOptions = mp.tasks.BaseOptions
    PoseLandmarker = mp.tasks.vision.PoseLandmarker
    PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
    RunningMode = mp.tasks.vision.RunningMode

    model_path = _get_pose_model_path(config)

    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=RunningMode.VIDEO,
        num_poses=int(getattr(config, "num_poses", 1)),
        min_pose_detection_confidence=float(getattr(config, "min_detection_confidence", 0.5)),
        min_pose_presence_confidence=float(getattr(config, "min_tracking_confidence", 0.5)),
        min_tracking_confidence=float(getattr(config, "min_tracking_confidence", 0.5)),
        output_segmentation_masks=False,
    )

    frames_2d: list[np.ndarray] = []
    frames_3d: list[np.ndarray] = []
    confs: list[np.ndarray] = []
    times: list[float] = []

    with PoseLandmarker.create_from_options(options) as landmarker:
        for frame_idx, frame in _iter_video_frames(video_path):
            if frame_idx % stride != 0:
                continue

            rgb = np.asarray(frame)[..., :3].copy()
            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb,
            )
            timestamp_ms = int(round((frame_idx / source_fps) * 1000.0))
            result = landmarker.detect_for_video(mp_image, timestamp_ms)

            lm2d = np.full((len(JOINT_NAMES), 2), np.nan, dtype=float)
            lm3d = np.full((len(JOINT_NAMES), 3), np.nan, dtype=float)
            conf = np.full((len(JOINT_NAMES),), np.nan, dtype=float)

            if result.pose_landmarks:
                pose_lm = result.pose_landmarks[0]
                for i, p in enumerate(pose_lm[: len(JOINT_NAMES)]):
                    lm2d[i, 0] = float(p.x)
                    lm2d[i, 1] = float(p.y)
                    conf[i] = float(getattr(p, "visibility", np.nan))

            if result.pose_world_landmarks:
                pose_world = result.pose_world_landmarks[0]
                for i, p in enumerate(pose_world[: len(JOINT_NAMES)]):
                    lm3d[i, 0] = float(p.x)
                    lm3d[i, 1] = float(p.y)
                    lm3d[i, 2] = float(p.z)
                    if not np.isfinite(conf[i]):
                        conf[i] = float(getattr(p, "visibility", np.nan))

            frames_2d.append(lm2d)
            frames_3d.append(lm3d)
            confs.append(conf)
            times.append(frame_idx / source_fps)

    time = np.asarray(times, dtype=float)
    conf_arr = np.asarray(confs, dtype=float)
    fps = source_fps / stride if stride > 0 else source_fps

    pose2d = Pose2DResult(
        name=f"{video_path.stem}_pose2d",
        data=np.asarray(frames_2d, dtype=float),
        time=time,
        landmark_names=JOINT_NAMES[:],
        dims=("x_norm", "y_norm"),
        confidence=conf_arr,
        metadata={
            "video_path": str(video_path),
            "backend": "mediapipe_tasks",
            "pose_model_path": str(model_path),
            "source_fps": source_fps,
            "width": meta["width"],
            "height": meta["height"],
        },
        source="mediapipe_tasks",
        fps=fps,
    )

    pose3d_world = Pose3DWorldResult(
        name=f"{video_path.stem}_pose3d_world",
        data=np.asarray(frames_3d, dtype=float),
        time=time,
        landmark_names=JOINT_NAMES[:],
        dims=("x_m", "y_m", "z_m"),
        confidence=conf_arr,
        metadata={
            "video_path": str(video_path),
            "backend": "mediapipe_tasks",
            "pose_model_path": str(model_path),
            "source_fps": source_fps,
            "width": meta["width"],
            "height": meta["height"],
        },
        source="mediapipe_tasks",
        fps=fps,
    )

    return pose2d, pose3d_world


def _infer_image_size_from_pose2d(pose2d: Pose2DResult | None) -> tuple[int, int]:
    width = 1920
    height = 1080

    if pose2d is None:
        return width, height

    metadata = pose2d.metadata or {}
    maybe_width = metadata.get("width")
    maybe_height = metadata.get("height")

    if maybe_width is not None and maybe_height is not None:
        try:
            width = int(maybe_width)
            height = int(maybe_height)
        except Exception:
            pass

    return width, height


def estimate_global_pose(
    pose3d_world: Pose3DWorldResult,
    pose2d: Pose2DResult | None = None,
    *,
    config: Pose3DGlobalConfig | None = None,
) -> Pose3DGlobalResult:
    config = config or Pose3DGlobalConfig()
    data = np.asarray(pose3d_world.data, dtype=float).copy()

    translation_method = getattr(config, "translation_method", "hip_center")

    if translation_method == "pnp" and pose2d is not None:
        try:
            import cv2  # type: ignore
        except Exception:
            translation_method = "hip_center"

    if translation_method == "pnp" and pose2d is not None:
        width, height = _infer_image_size_from_pose2d(pose2d)
        fx = fy = float(config.focal_length_factor) * max(width, height)
        cx = width / 2.0
        cy = height / 2.0
        camera_matrix = np.array(
            [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
        dist = np.zeros((4, 1), dtype=np.float64)

        #try:
        import cv2  # type: ignore

        for f in range(data.shape[0]):
            obj = np.asarray(pose3d_world.data[f], dtype=np.float64)
            img = np.asarray(pose2d.data[f], dtype=np.float64).copy()

            valid = np.isfinite(obj).all(axis=1) & np.isfinite(img).all(axis=1)

            if pose2d.confidence is not None:
                valid &= np.nan_to_num(pose2d.confidence[f], nan=0.0) >= float(config.pnp_confidence_threshold)

            if int(valid.sum()) < int(config.pnp_min_points):
                continue

            object_points = obj[valid]
            image_points = img[valid]
            image_points[:, 0] *= width
            image_points[:, 1] *= height

            ok, rvec, tvec = cv2.solvePnP(
                object_points,
                image_points,
                camera_matrix,
                dist,
                flags=cv2.SOLVEPNP_EPNP,
            )
            if not ok:
                continue

            rot, _ = cv2.Rodrigues(rvec)
            transformed = (rot @ obj.T).T + tvec.reshape(1, 3)
            data[f] = transformed

        #except Exception:
         #   translation_method = "hip_center"
          #  print("Warning: OpenCV not available, falling back to hip_center translation method")

    if translation_method != "pnp":
        lhip = NAME_TO_INDEX["left_hip"]
        rhip = NAME_TO_INDEX["right_hip"]
        root = np.nanmean(data[:, [lhip, rhip], :], axis=1)

        valid_root = np.isfinite(root).all(axis=1)
        if np.any(valid_root):
            data[valid_root] = data[valid_root] - root[valid_root, None, :]

    foot_indices = [NAME_TO_INDEX[name] for name in FOOT_MARKERS if name in NAME_TO_INDEX]
    foot_y = data[:, foot_indices, 1].reshape(-1)
    foot_y = foot_y[np.isfinite(foot_y)]

    if len(foot_y):
        floor_y = float(np.nanmedian(foot_y))
    else:
        finite_y = data[:, :, 1][np.isfinite(data[:, :, 1])]
        floor_y = float(np.nanmin(finite_y)) if len(finite_y) else 0.0

    global_data = np.empty_like(data)
    global_data[:, :, 0] = data[:, :, 0]
    global_data[:, :, 1] = floor_y - data[:, :, 1]
    global_data[:, :, 2] = data[:, :, 2]

    result = Pose3DGlobalResult(
        name=pose3d_world.name.replace("_world", "_global"),
        data=global_data,
        time=pose3d_world.time.copy(),
        landmark_names=pose3d_world.landmark_names[:],
        dims=("x_m", "y_m", "z_m"),
        confidence=None if pose3d_world.confidence is None else pose3d_world.confidence.copy(),
        metadata={
            **(pose3d_world.metadata or {}),
            "floor_method": getattr(config, "floor_method", "median_foot_y"),
            "translation_method": translation_method,
            "floor_y": floor_y,
        },
        source=pose3d_world.source,
        fps=pose3d_world.fps,
    )

    if getattr(config, "smooth_root", False):
        result = result.smooth(
            method="butterworth",
            cutoff_hz=float(getattr(config, "root_smoothing_cutoff_hz", 6.0)),
        )

    return result
