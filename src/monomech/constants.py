"""Shared biomechanical constants."""

from __future__ import annotations

LANDMARK_NAMES = [
    "nose",
    "left_eye_inner", "left_eye", "left_eye_outer",
    "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear",
    "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
    "left_pinky", "right_pinky",
    "left_index", "right_index",
    "left_thumb", "right_thumb",
    "left_hip", "right_hip",
    "left_knee", "right_knee",
    "left_ankle", "right_ankle",
    "left_heel", "right_heel",
    "left_foot_index", "right_foot_index",
]

LANDMARK_INDEX = {name: idx for idx, name in enumerate(LANDMARK_NAMES)}

POSE_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3),
    (0, 4), (4, 5), (5, 6),
    (9, 10),
    (11, 12),
    (11, 13), (13, 15), (15, 17), (15, 19), (15, 21),
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (27, 29), (27, 31), (29, 31),
    (24, 26), (26, 28), (28, 30), (28, 32), (30, 32),
]

LEFT_HIP = LANDMARK_INDEX["left_hip"]
RIGHT_HIP = LANDMARK_INDEX["right_hip"]
LEFT_SHOULDER = LANDMARK_INDEX["left_shoulder"]
RIGHT_SHOULDER = LANDMARK_INDEX["right_shoulder"]
LEFT_KNEE = LANDMARK_INDEX["left_knee"]
RIGHT_KNEE = LANDMARK_INDEX["right_knee"]
LEFT_ANKLE = LANDMARK_INDEX["left_ankle"]
RIGHT_ANKLE = LANDMARK_INDEX["right_ankle"]
LEFT_HEEL = LANDMARK_INDEX["left_heel"]
RIGHT_HEEL = LANDMARK_INDEX["right_heel"]
LEFT_FOOT_INDEX = LANDMARK_INDEX["left_foot_index"]
RIGHT_FOOT_INDEX = LANDMARK_INDEX["right_foot_index"]

FOOT_LANDMARKS = [LEFT_ANKLE, RIGHT_ANKLE, LEFT_HEEL, RIGHT_HEEL, LEFT_FOOT_INDEX, RIGHT_FOOT_INDEX]
HIP_LANDMARKS = [LEFT_HIP, RIGHT_HIP]
SHOULDER_LANDMARKS = [LEFT_SHOULDER, RIGHT_SHOULDER]
PNP_PRIORITY_LANDMARKS = [
    LEFT_HIP, RIGHT_HIP, LEFT_SHOULDER, RIGHT_SHOULDER,
    LEFT_KNEE, RIGHT_KNEE, LEFT_ANKLE, RIGHT_ANKLE,
    LEFT_HEEL, RIGHT_HEEL, LEFT_FOOT_INDEX, RIGHT_FOOT_INDEX,
]
