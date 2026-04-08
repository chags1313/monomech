from __future__ import annotations

from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def stem_or_name(path: str | Path) -> str:
    p = Path(path)
    return p.stem if p.suffix else p.name
