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


def _indices_for_names(landmark_names: list[str], names: list[str]) -> tuple[list[int], list[str]]:
    index = {name: i for i, name in enumerate(landmark_names)}
    lower_index = {name.lower(): i for i, name in enumerate(landmark_names)}
    indices: list[int] = []
    resolved: list[str] = []
    for name in names:
        idx = index.get(name)
        if idx is None:
            idx = lower_index.get(name.lower())
        if idx is not None:
            indices.append(idx)
            resolved.append(landmark_names[idx])
    return indices, resolved


def _percentile(value: float | None, *, default: float) -> float:
    if value is None:
        return default
    try:
        p = float(value)
    except Exception:
        return default
    if 0.0 < p <= 1.0:
        p *= 100.0
    return float(np.clip(p, 0.0, 100.0))


def _infer_raw_y_direction(data: np.ndarray, landmark_names: list[str]) -> float:
    foot_indices, _ = _indices_for_names(landmark_names, FOOT_MARKERS)
    hip_indices, _ = _indices_for_names(landmark_names, ["left_hip", "right_hip"])
    if not foot_indices or not hip_indices:
        return 1.0

    foot_y = data[:, foot_indices, 1].reshape(-1)
    hip_y = data[:, hip_indices, 1].reshape(-1)
    foot_y = foot_y[np.isfinite(foot_y)]
    hip_y = hip_y[np.isfinite(hip_y)]
    if not len(foot_y) or not len(hip_y):
        return 1.0

    # OpenCV/PnP camera coordinates use positive Y downward, while some upstream
    # world-landmark sources use positive Y upward. Compare hips and feet so the
    # exported result is consistently Y-up either way.
    return 1.0 if float(np.nanmedian(foot_y) - np.nanmedian(hip_y)) >= 0.0 else -1.0


def _framewise_foot_speed(foot_data: np.ndarray, time: np.ndarray) -> np.ndarray:
    n_frames, n_feet = foot_data.shape[:2]
    speed = np.full((n_frames, n_feet), np.nan, dtype=float)
    if n_frames < 2:
        return speed

    dt = np.diff(np.asarray(time, dtype=float))
    dt[~np.isfinite(dt) | (dt <= 0.0)] = np.nan
    delta = np.linalg.norm(np.diff(foot_data, axis=0), axis=2)
    interval_speed = delta / dt[:, None]
    interval_speed[~np.isfinite(interval_speed)] = np.nan

    speed[0] = interval_speed[0]
    speed[-1] = interval_speed[-1]
    if n_frames > 2:
        speed[1:-1] = np.nanmin(
            np.stack([interval_speed[:-1], interval_speed[1:]], axis=0),
            axis=0,
        )
    return speed


def _trim_upper_outliers(values: np.ndarray, *, min_samples: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size < max(8, min_samples):
        return values
    q1, q3 = np.nanpercentile(values, [25.0, 75.0])
    iqr = q3 - q1
    if not np.isfinite(iqr) or iqr <= 0.0:
        return values
    trimmed = values[values <= q3 + 1.5 * iqr]
    return trimmed if trimmed.size >= min_samples else values


def _estimate_floor_y(
    data: np.ndarray,
    landmark_names: list[str],
    confidence: np.ndarray | None,
    time: np.ndarray,
    config: Pose3DGlobalConfig,
) -> tuple[float, float, dict]:
    method = str(getattr(config, "floor_method", "auto") or "auto")
    y_direction = _infer_raw_y_direction(data, landmark_names)
    direction_name = "down" if y_direction > 0.0 else "up"
    metadata: dict = {
        "floor_method_requested": method,
        "input_y_direction": direction_name,
    }

    if method == "none":
        metadata.update(
            {
                "floor_method": "none",
                "floor_contact_samples": 0,
                "floor_contact_frames": 0,
            }
        )
        return 0.0, y_direction, metadata

    foot_indices, foot_names = _indices_for_names(landmark_names, FOOT_MARKERS)
    finite_y = data[:, :, 1][np.isfinite(data[:, :, 1])]
    if not foot_indices:
        floor_score = float(np.nanmax(y_direction * finite_y)) if len(finite_y) else 0.0
        metadata.update(
            {
                "floor_method": "finite_y_fallback",
                "floor_contact_samples": 0,
                "floor_contact_frames": 0,
                "floor_marker_names": [],
            }
        )
        return y_direction * floor_score, y_direction, metadata

    foot_data = np.asarray(data[:, foot_indices, :], dtype=float)
    foot_score = y_direction * foot_data[:, :, 1]
    valid = np.isfinite(foot_data).all(axis=2) & np.isfinite(foot_score)
    if confidence is not None:
        foot_conf = np.asarray(confidence[:, foot_indices], dtype=float)
        valid &= (
            np.nan_to_num(foot_conf, nan=0.0)
            >= float(getattr(config, "floor_confidence_threshold", 0.0))
        )

    scores = foot_score[valid]
    if scores.size == 0:
        floor_score = float(np.nanmax(y_direction * finite_y)) if len(finite_y) else 0.0
        metadata.update(
            {
                "floor_method": "finite_y_fallback",
                "floor_contact_samples": 0,
                "floor_contact_frames": 0,
                "floor_marker_names": foot_names,
            }
        )
        return y_direction * floor_score, y_direction, metadata

    floor_percentile = _percentile(getattr(config, "floor_percentile", None), default=90.0)

    if method == "feet_median":
        floor_score = float(np.nanmedian(scores))
        metadata.update(
            {
                "floor_method": "feet_median",
                "floor_contact_samples": int(scores.size),
                "floor_contact_frames": int(np.any(valid, axis=1).sum()),
                "floor_marker_names": foot_names,
            }
        )
        return y_direction * floor_score, y_direction, metadata

    if method == "min_y":
        floor_score = float(np.nanmax(scores))
        metadata.update(
            {
                "floor_method": "min_y",
                "floor_contact_samples": int(scores.size),
                "floor_contact_frames": int(np.any(valid, axis=1).sum()),
                "floor_marker_names": foot_names,
            }
        )
        return y_direction * floor_score, y_direction, metadata

    speed = _framewise_foot_speed(foot_data, time)
    speed_values = speed[valid & np.isfinite(speed)]
    min_samples = max(1, int(getattr(config, "floor_min_contact_samples", 6)))
    velocity_threshold = None
    contact = valid.copy()

    if speed_values.size >= min_samples:
        velocity_percentile = _percentile(
            getattr(config, "floor_contact_velocity_percentile", None),
            default=35.0,
        )
        velocity_threshold = float(np.nanpercentile(speed_values, velocity_percentile))
        contact = valid & np.isfinite(speed) & (speed <= velocity_threshold)

    if int(contact.sum()) >= min_samples:
        contact_scores = foot_score[contact]
        height_percentile = _percentile(
            getattr(config, "floor_contact_height_percentile", None),
            default=35.0,
        )
        height_threshold = float(np.nanpercentile(contact_scores, height_percentile))
        support_contact = contact & (foot_score >= height_threshold)
        if int(support_contact.sum()) >= min_samples:
            contact = support_contact
    else:
        contact = np.zeros_like(valid, dtype=bool)

    if int(contact.sum()) >= min_samples:
        contact_scores = _trim_upper_outliers(foot_score[contact], min_samples=min_samples)
        floor_score = float(np.nanpercentile(contact_scores, floor_percentile))
        resolved_method = "foot_contact"
    else:
        contact_scores = _trim_upper_outliers(scores, min_samples=min_samples)
        floor_score = float(np.nanpercentile(contact_scores, floor_percentile))
        resolved_method = "feet_percentile_fallback"
        contact = valid

    metadata.update(
        {
            "floor_method": resolved_method,
            "floor_contact_samples": int(contact.sum()),
            "floor_contact_frames": int(np.any(contact, axis=1).sum()),
            "floor_marker_names": foot_names,
            "floor_percentile": floor_percentile,
            "floor_velocity_threshold_m_per_s": velocity_threshold,
        }
    )
    return y_direction * floor_score, y_direction, metadata


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

    floor_y, y_direction, floor_metadata = _estimate_floor_y(
        data,
        pose3d_world.landmark_names,
        pose3d_world.confidence,
        pose3d_world.time,
        config,
    )

    global_data = np.empty_like(data)
    global_data[:, :, 0] = data[:, :, 0]
    global_data[:, :, 1] = y_direction * (floor_y - data[:, :, 1])
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
            **floor_metadata,
            "translation_method": translation_method,
            "floor_y": floor_y,
            "floored": floor_metadata.get("floor_method") != "none",
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
