"""Notebook-first trial object with lazy stage caching."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .io.video import open_video_metadata


@dataclass(slots=True)
class Trial:
    """Represents a single monocular biomechanics trial."""

    video_path: Path
    name: str
    fps: float
    width: int
    height: int
    duration_s: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    stage_results: dict[str, Any] = field(default_factory=dict, repr=False)
    _mediapipe_extraction: Any | None = field(default=None, repr=False)

    @classmethod
    def from_video(cls, video_path: str | Path, **metadata: Any) -> "Trial":
        meta = open_video_metadata(video_path)
        return cls(
            video_path=meta.path,
            name=meta.path.stem,
            fps=meta.fps,
            width=meta.width,
            height=meta.height,
            duration_s=meta.duration_s,
            metadata={
                "n_frames": meta.n_frames,
                "duration_s": meta.duration_s,
                **metadata,
            },
        )

    def register_stage(self, name: str, result: Any) -> Any:
        self.stage_results[name] = result
        return result

    def get_stage(self, name: str, default: Any = None) -> Any:
        return self.stage_results.get(name, default)

    @property
    def video_metadata(self) -> dict[str, Any]:
        return {
            "video_path": str(self.video_path),
            "name": self.name,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "duration_s": self.duration_s,
            **self.metadata,
        }
