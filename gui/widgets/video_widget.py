"""
VideoWidget — отображает кадры numpy (BGR) в окне PyQt6.
Получает кадры через слот `update_frame(frame)`.
"""
from __future__ import annotations

import cv2
import numpy as np
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QSizePolicy


class VideoWidget(QLabel):
    """Простой виджет-«экран» для видеопотока."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #111; color: #888;")
        self.setText("Нет сигнала")

        self._last_pixmap: QPixmap | None = None

    @pyqtSlot(np.ndarray)
    def update_frame(self, frame: np.ndarray) -> None:
        """
        Принимает BGR-кадр (как отдаёт OpenCV) и рисует в виджете.
        """
        if frame is None or frame.size == 0:
            return

        # BGR -> RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w

        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        # масштабируем под размер виджета (с сохранением пропорций)
        self._last_pixmap = pixmap
        self.setPixmap(
            pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        """При ресайзе окна — пересчитываем масштаб последнего кадра."""
        if self._last_pixmap is not None:
            self.setPixmap(
                self._last_pixmap.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        super().resizeEvent(event)