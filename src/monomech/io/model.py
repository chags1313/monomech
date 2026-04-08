from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd


def inspect_model_markers(model_path: str | Path) -> pd.DataFrame:
    model_path = Path(model_path)
    tree = ET.parse(model_path)
    root = tree.getroot()
    rows: list[dict] = []
    for marker in root.iter():
        if marker.tag.lower().endswith("marker"):
            name = marker.attrib.get("name", "")
            parent_frame = None
            location = None
            for child in marker:
                tag = child.tag.lower()
                if tag.endswith("socket_parent_frame") or tag.endswith("body"):
                    parent_frame = (child.text or "").strip()
                elif tag.endswith("location"):
                    location = (child.text or "").strip()
            rows.append(
                {
                    "marker_name": name,
                    "parent_frame": parent_frame,
                    "location": location,
                }
            )
    if not rows:
        # fallback: some models store MarkerSet/ObjectGroup names differently
        for obj in root.iter():
            if obj.attrib.get("name") and "marker" in obj.tag.lower():
                rows.append({"marker_name": obj.attrib["name"], "parent_frame": None, "location": None})
    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)


def build_marker_map(
    pose_landmarks: list[str],
    model_markers: list[str],
    *,
    strategy: str = "name_match",
) -> dict[str, str]:
    pose_lookup = {name.lower(): name for name in pose_landmarks}
    mapping: dict[str, str] = {}
    for marker in model_markers:
        key = marker.lower()
        if strategy == "name_match" and key in pose_lookup:
            mapping[pose_lookup[key]] = marker
            continue
        normalized = key.replace(" ", "_")
        if normalized in pose_lookup:
            mapping[pose_lookup[normalized]] = marker
            continue
        normalized = normalized.replace("left_", "l_").replace("right_", "r_")
        if normalized in pose_lookup:
            mapping[pose_lookup[normalized]] = marker
    return mapping
