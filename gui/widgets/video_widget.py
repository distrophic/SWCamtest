"""
VideoWidget — отображает кадры numpy (BGR) в окне PyQt6.
Получает кадры через слот `update_frame(frame)`.
Может рисовать поверх кадра bounding boxes от детектора.
"""
from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QRect, QRectF, QSize, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QImage, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QSizePolicy

from core.detections import box_kind
from utils.logger import get_logger

logger = get_logger(__name__)


class VideoWidget(QLabel):
    """Виджет-«экран» для видеопотока с оверлеем детекций."""

    activated = pyqtSignal()
    zone_changed = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #111; color: #888;")
        self.setText("Нет сигнала")

        self._last_frame: np.ndarray | None = None
        self._image: QImage | None = None
        self._pending: np.ndarray | None = None
        self._scheduled = False
        # Последние детекции: список кортежей (x1, y1, x2, y2, conf)
        self._detections: list[tuple[int, int, int, int, float]] = []
        self._zone: tuple[float, float, float, float] | None = None
        self._zone_arm = False
        self._drag_origin: tuple[float, float] | None = None
        self._drag_now: tuple[float, float] | None = None

    def sizeHint(self) -> QSize:  # noqa: N802
        # Иначе QLabel подстраивает окно под каждый кадр и картинка дёргается.
        return QSize(640, 360)

    def last_frame(self) -> np.ndarray | None:
        """Копия последнего исходного кадра, без рамок детектора."""
        if self._last_frame is None:
            return None
        return self._last_frame.copy()

    # ── Слоты ─────────────────────────────────────────────────
    def set_zone(self, zone: tuple[float, float, float, float] | None) -> None:
        self._zone = zone
        self.update()

    def set_zone_arm(self, armed: bool) -> None:
        self._zone_arm = bool(armed)
        if not armed:
            self._drag_origin = None
            self._drag_now = None
            self.update()

    @pyqtSlot(list)
    def set_detections(self, boxes: list) -> None:
        """Принимает боксы от детектора. Рисуются поверх кадра."""
        self._detections = boxes
        self.update()

    @pyqtSlot(object)
    def update_frame(self, frame: np.ndarray) -> None:
        """Кладёт кадр в очередь из одного места: на экран попадает самый свежий."""
        if frame is None or getattr(frame, "size", 0) == 0:
            return
        if frame.ndim != 3 or frame.shape[2] != 3:
            logger.warning(f"Кадр неожиданной формы {getattr(frame, 'shape', None)}, пропуск")
            return

        self._pending = frame
        if self._scheduled:
            return
        self._scheduled = True
        QTimer.singleShot(0, self._present)

    def _present(self) -> None:
        self._scheduled = False
        frame = self._pending
        self._pending = None
        if frame is None:
            return
        try:
            self._show_frame(frame)
        except Exception:
            logger.exception("Не удалось нарисовать кадр")
        if self._pending is not None and not self._scheduled:
            self._scheduled = True
            QTimer.singleShot(0, self._present)

    def _show_frame(self, frame: np.ndarray) -> None:
        owned = np.ascontiguousarray(frame)
        self._last_frame = owned
        height, width, _channels = owned.shape
        image = QImage(
            owned.data,
            width,
            height,
            int(owned.strides[0]),
            QImage.Format.Format_BGR888,
        ).copy()
        self._image = image
        if self.text():
            self.setText("")
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._image is None:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111111"))
        target = self._image_rect()
        if target is None:
            return
        painter.drawImage(target, self._image)
        self._paint_boxes(painter, target)
        zone = self._drag_rect() or self._zone
        if zone is not None:
            painter.setPen(QPen(QColor("#fc4"), 2))
            painter.drawRect(self._norm_rect(zone))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._zone_arm and event.button() == Qt.MouseButton.LeftButton:
            origin = self._event_norm(event)
            self._drag_origin = origin
            self._drag_now = origin
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._zone_arm and self._drag_origin is not None:
            self._drag_now = self._event_norm(event) or self._drag_now
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._zone_arm and event.button() == Qt.MouseButton.LeftButton:
            zone = self._drag_rect()
            self._drag_origin = None
            self._drag_now = None
            if zone is not None:
                self._zone = zone
                self.zone_changed.emit(zone)
            self.update()
            return
        super().mouseReleaseEvent(event)

    def _paint_boxes(self, painter: QPainter, target: QRect) -> None:
        frame = self._last_frame
        if frame is None or not self._detections:
            return
        frame_height, frame_width = frame.shape[:2]
        if frame_width <= 0 or frame_height <= 0:
            return
        for box in self._detections:
            x1, y1, x2, y2, conf = box[:5]
            person = box_kind(box) == "person"
            color = QColor("#00cc00") if person else QColor("#ee8800")
            title = "человек" if person else "сущность"
            left = target.x() + x1 / frame_width * target.width()
            top = target.y() + y1 / frame_height * target.height()
            right = target.x() + x2 / frame_width * target.width()
            bottom = target.y() + y2 / frame_height * target.height()
            painter.setPen(QPen(color, 2))
            painter.drawRect(QRectF(left, top, right - left, bottom - top))
            label = f"{title} {conf:.2f}"
            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(label)
            text_height = metrics.height()
            background = QRectF(left, top - text_height - 2, text_width + 8, text_height + 2)
            painter.fillRect(background, color)
            painter.setPen(QColor("#000000"))
            painter.drawText(int(background.x() + 4), int(background.bottom() - 4), label)

    def _image_rect(self) -> QRect | None:
        if self._image is None:
            return None
        target = self._image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = (self.width() - target.width()) // 2
        y = (self.height() - target.height()) // 2
        return QRect(x, y, max(target.width(), 1), max(target.height(), 1))

    def _event_norm(self, event) -> tuple[float, float] | None:
        rect = self._image_rect()
        if rect is None:
            return None
        pos = event.position()
        if not rect.contains(int(pos.x()), int(pos.y())):
            return None
        return (
            min(max((pos.x() - rect.x()) / rect.width(), 0.0), 1.0),
            min(max((pos.y() - rect.y()) / rect.height(), 0.0), 1.0),
        )

    def _drag_rect(self) -> tuple[float, float, float, float] | None:
        if self._drag_origin is None or self._drag_now is None:
            return None
        x0, y0 = self._drag_origin
        x1, y1 = self._drag_now
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))
        width = right - left
        height = bottom - top
        if width < 0.03 or height < 0.03:
            return None
        return (left, top, width, height)

    def _norm_rect(self, zone: tuple[float, float, float, float]) -> QRect:
        rect = self._image_rect() or QRect(0, 0, self.width(), self.height())
        return QRect(
            int(rect.x() + zone[0] * rect.width()),
            int(rect.y() + zone[1] * rect.height()),
            max(int(zone[2] * rect.width()), 1),
            max(int(zone[3] * rect.height()), 1),
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().resizeEvent(event)
