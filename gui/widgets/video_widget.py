"""
VideoWidget — отображает кадры numpy (BGR) в окне PyQt6.
Получает кадры через слот `update_frame(frame)`.
Может рисовать поверх кадра bounding boxes от детектора.
"""
from __future__ import annotations

import cv2
import numpy as np
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QSizePolicy


class VideoWidget(QLabel):
    """Виджет-«экран» для видеопотока с оверлеем детекций."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #111; color: #888;")
        self.setText("Нет сигнала")

        self._last_pixmap: QPixmap | None = None
        # Последние детекции: список кортежей (x1, y1, x2, y2, conf)
        self._detections: list[tuple[int, int, int, int, float]] = []

    # ── Слоты ─────────────────────────────────────────────────
    @pyqtSlot(list)
    def set_detections(self, boxes: list) -> None:
        """Принимает боксы от детектора. Рисуются при следующем кадре."""
        self._detections = boxes

    @pyqtSlot(np.ndarray)
    def update_frame(self, frame: np.ndarray) -> None:
        """Принимает BGR-кадр и рисует его + оверлей детекций."""
        if frame is None or frame.size == 0:
            return

        # Копируем, чтобы не портить оригинал (его ещё детектор обрабатывает)
        annotated = frame.copy()

        # ── Рисуем боксы (в BGR!) ──
        for (x1, y1, x2, y2, conf) in self._detections:
            # Зелёная рамка
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Подпись с confidence
            label = f"person {conf:.2f}"
            (tw, th), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            # Фон под текст
            cv2.rectangle(
                annotated,
                (x1, y1 - th - 6),
                (x1 + tw + 4, y1),
                (0, 255, 0),
                -1,
            )
            # Сам текст (чёрный поверх зелёного)
            cv2.putText(
                annotated,
                label,
                (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1,
                cv2.LINE_AA,
            )

        # BGR → RGB для Qt
        rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w

        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        self._last_pixmap = pixmap
        self.setPixmap(
            pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        if self._last_pixmap is not None:
            self.setPixmap(
                self._last_pixmap.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        super().resizeEvent(event)