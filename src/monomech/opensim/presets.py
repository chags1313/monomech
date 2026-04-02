"""Model-specific OpenSim presets and landmark-to-marker approximations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping
import xml.etree.ElementTree as ET

import numpy as np

from ..constants import LANDMARK_INDEX
from ..types import PoseSequence3D

MarkerResolver = str | tuple[str, ...] | Callable[[PoseSequence3D, int], np.ndarray]


def _mean_points(pose: PoseSequence3D, frame_idx: int, names: list[str]) -> np.ndarray:
    pts = []
    for name in names:
        idx = LANDMARK_INDEX.get(name)
        if idx is None:
            continue
        pt = pose.xyz[frame_idx, idx]
        if np.isfinite(pt).all():
            pts.append(pt)
    if not pts:
        return np.full(3, np.nan, dtype=float)
    return np.nanmean(np.vstack(pts), axis=0)


def _sternum(pose: PoseSequence3D, frame_idx: int) -> np.ndarray:
    shoulders = _mean_points(pose, frame_idx, ["left_shoulder", "right_shoulder"])
    hips = _mean_points(pose, frame_idx, ["left_hip", "right_hip"])
    if np.isfinite(shoulders).all() and np.isfinite(hips).all():
        return shoulders * 0.7 + hips * 0.3
    return shoulders


def _clavicle(pose: PoseSequence3D, frame_idx: int) -> np.ndarray:
    return _mean_points(pose, frame_idx, ["left_shoulder", "right_shoulder"])


def _c7(pose: PoseSequence3D, frame_idx: int) -> np.ndarray:
    clav = _clavicle(pose, frame_idx)
    left_ear = _mean_points(pose, frame_idx, ["left_ear"])
    right_ear = _mean_points(pose, frame_idx, ["right_ear"])
    ear_mid = _mean_points(pose, frame_idx, ["left_ear", "right_ear"])
    if np.isfinite(clav).all() and np.isfinite(ear_mid).all():
        out = clav * 0.75 + ear_mid * 0.25
        if np.isfinite(left_ear).all() and np.isfinite(right_ear).all():
            shoulder_span = _mean_points(pose, frame_idx, ["left_shoulder"]) - _mean_points(pose, frame_idx, ["right_shoulder"])
            if np.isfinite(shoulder_span).all():
                posterior = np.cross(shoulder_span, np.array([0.0, 1.0, 0.0]))
                n = np.linalg.norm(posterior)
                if n > 1e-8:
                    out = out - 0.02 * posterior / n
        return out
    return clav


def _t10(pose: PoseSequence3D, frame_idx: int) -> np.ndarray:
    stern = _sternum(pose, frame_idx)
    hips = _mean_points(pose, frame_idx, ["left_hip", "right_hip"])
    if np.isfinite(stern).all() and np.isfinite(hips).all():
        return stern * 0.35 + hips * 0.65
    return hips


def _rear_pelvis(side: str):
    def _resolver(pose: PoseSequence3D, frame_idx: int) -> np.ndarray:
        hip = _mean_points(pose, frame_idx, [f"{side}_hip"])
        other = _mean_points(pose, frame_idx, ["left_hip" if side == "right" else "right_hip"])
        shoulders = _mean_points(pose, frame_idx, ["left_shoulder", "right_shoulder"])
        if not np.isfinite(hip).all():
            return hip
        offset = np.zeros(3, dtype=float)
        if np.isfinite(other).all() and np.isfinite(shoulders).all():
            lateral = hip - other
            vertical = shoulders - _mean_points(pose, frame_idx, ["left_hip", "right_hip"])
            posterior = np.cross(lateral, vertical)
            n = np.linalg.norm(posterior)
            if n > 1e-8:
                offset = -0.03 * posterior / n
        return hip + offset
    return _resolver


@dataclass(slots=True)
class OpenSimModelPreset:
    name: str
    body_map: dict[str, str] = field(default_factory=dict)
    marker_map: dict[str, MarkerResolver] = field(default_factory=dict)

    def marker_names(self) -> list[str]:
        return list(self.marker_map)


GATMA_BODY_MAP: dict[str, str] = {
    "pelvis": "pelvis",
    "sacrum": "sacrum",
    "trunk": "torso",
    "torso": "torso",
    "head": "head",
    "abdomen": "Abdomen",
    "right_thigh": "femur_r",
    "left_thigh": "femur_l",
    "right_shank": "tibia_r",
    "left_shank": "tibia_l",
    "right_talus": "talus_r",
    "left_talus": "talus_l",
    "right_foot": "calcn_r",
    "left_foot": "calcn_l",
    "right_toes": "toes_r",
    "left_toes": "toes_l",
    "right_upper_arm": "humerus_r",
    "left_upper_arm": "humerus_l",
    "right_forearm": "radius_r",
    "left_forearm": "radius_l",
    "right_hand": "hand_r",
    "left_hand": "hand_l",
}

GATMA_MARKER_MAP: dict[str, MarkerResolver] = {
    "RSHO": "right_shoulder",
    "LSHO": "left_shoulder",
    "RELB": "right_elbow",
    "LELB": "left_elbow",
    "RWRA": "right_wrist",
    "RWRB": "right_wrist",
    "LWRA": "left_wrist",
    "LWRB": "left_wrist",
    "RFIN": "right_index",
    "LFIN": "left_index",
    "STRN": _sternum,
    "CLAV": _clavicle,
    "C7": _c7,
    "T10": _t10,
    "RASI": "right_hip",
    "LASI": "left_hip",
    "RPSI": _rear_pelvis("right"),
    "LPSI": _rear_pelvis("left"),
    "RFHD": ("right_eye", "right_eye_outer"),
    "LFHD": ("left_eye", "left_eye_outer"),
    "RBHD": "right_ear",
    "LBHD": "left_ear",
    "RKNE": "right_knee",
    "LKNE": "left_knee",
    "RANK": "right_ankle",
    "LANK": "left_ankle",
    "RHEE": "right_heel",
    "LHEE": "left_heel",
    "RTOE": "right_foot_index",
    "LTOE": "left_foot_index",
}

GATMA_PRESET = OpenSimModelPreset(name="gatma_exact", body_map=GATMA_BODY_MAP, marker_map=GATMA_MARKER_MAP)


def resolve_marker_point(pose: PoseSequence3D, frame_idx: int, resolver: MarkerResolver) -> np.ndarray:
    if callable(resolver):
        out = np.asarray(resolver(pose, frame_idx), dtype=float).reshape(3)
        return out
    if isinstance(resolver, str):
        idx = LANDMARK_INDEX[resolver]
        return pose.xyz[frame_idx, idx].astype(float)
    return _mean_points(pose, frame_idx, list(resolver))


def parse_model_marker_names(model_path: str | Path) -> list[str]:
    path = Path(model_path)
    if not path.exists():
        return []
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return []
    names: list[str] = []
    for elem in root.iter():
        if elem.tag.endswith("Marker") and elem.attrib.get("name"):
            name = elem.attrib.get("name")
            if name and name.lower() != "markerset":
                names.append(name)
    return names


def infer_model_preset(model_path: str | Path | None, model_preset: str | None = "auto") -> OpenSimModelPreset | None:
    if model_preset in {None, "none"}:
        return None
    if model_preset in {"gatma", "gatma_exact"}:
        return GATMA_PRESET
    if model_path is None:
        return None
    path = Path(model_path)
    if "gatma" in path.name.lower():
        return GATMA_PRESET
    marker_names = set(parse_model_marker_names(path))
    if marker_names and len(marker_names.intersection(GATMA_PRESET.marker_map)) >= 10:
        return GATMA_PRESET
    return None
