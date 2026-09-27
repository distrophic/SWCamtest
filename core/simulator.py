"""Режим без камеры: крутит заранее записанный ролик по кругу."""

from __future__ import annotations

import threading
from pathlib import Path

SIMULATOR_SOURCE = "simulator"
DEMO_CLIP = Path(__file__).resolve().parents[1] / "assets" / "demo" / "demo.mp4"
_LOCK = threading.Lock()


def is_simulator(source: int | str) -> bool:
    return isinstance(source, str) and source.strip().lower() == SIMULATOR_SOURCE


def ensure_demo_clip() -> Path:
    """Создаёт короткий ролик, если его ещё нет. Камера для этого не нужна."""
    with _LOCK:
        if DEMO_CLIP.is_file() and DEMO_CLIP.stat().st_size > 0:
            return DEMO_CLIP
        DEMO_CLIP.parent.mkdir(parents=True, exist_ok=True)
        _write_demo_clip(DEMO_CLIP)
    return DEMO_CLIP


def resolve_source(source: int | str) -> int | str:
    if is_simulator(source):
        return str(ensure_demo_clip())
    return source


def _write_demo_clip(path: Path) -> None:
    import cv2
    import numpy as np

    width, height, fps, frames = 320, 240, 10, 30
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise OSError(f"Не удалось записать симулятор: {path}")
    try:
        for index in range(frames):
            frame = np.full((height, width, 3), 36, dtype=np.uint8)
            x = (index * 8) % (width - 48)
            cv2.rectangle(frame, (x, 80), (x + 48, 150), (40, 170, 60), -1)
            cv2.putText(
                frame,
                "simulator",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (230, 230, 230),
                1,
                cv2.LINE_AA,
            )
            writer.write(frame)
    finally:
        writer.release()
