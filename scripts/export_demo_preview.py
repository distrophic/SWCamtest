"""Сохраняет docs/preview.png из виджета видео. Камера и модель не нужны."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui.widgets.video_widget import VideoWidget  # noqa: E402

OUTPUT = ROOT / "docs" / "preview.png"


def _scene() -> np.ndarray:
    frame = np.full((360, 640, 3), 28, dtype=np.uint8)
    cv2.rectangle(frame, (80, 120), (180, 280), (50, 160, 70), -1)
    cv2.putText(
        frame,
        "synthetic",
        (24, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (220, 220, 220),
        2,
        cv2.LINE_AA,
    )
    return frame


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    window = QWidget()
    window.setWindowTitle("SecureWatch")
    window.resize(720, 480)
    layout = QVBoxLayout(window)
    title = QLabel("SecureWatch — синтетический кадр, не запись с камеры")
    video = VideoWidget()
    video.set_detections([(80, 120, 180, 280, 0.86)])
    video.update_frame(_scene())
    layout.addWidget(title)
    layout.addWidget(video, stretch=1)
    window.show()
    app.processEvents()
    window.grab().save(str(OUTPUT))
    print(OUTPUT)


if __name__ == "__main__":
    main()
