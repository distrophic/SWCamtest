"""YOLOv8 детектор людей."""

import threading
import time

import numpy as np
from PyQt6.QtCore import QObject, Qt, pyqtSignal, pyqtSlot

from core.detections import WATCH_CLASSES, detection_kind
from utils.logger import get_logger

logger = get_logger(__name__)


class PersonDetector(QObject):
    detections_ready = pyqtSignal(list)
    error = pyqtSignal(str)
    ready = pyqtSignal()
    # object, не np.ndarray: Qt при QueuedConnection сам конвертирует массив
    # и на Windows отдаёт буфер, который следующий read() камеры уже освободил.
    _infer_requested = pyqtSignal(object)

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf: float = 0.4,
        classes: list[int] | None = None,
        min_interval: float = 0.2,
    ):
        super().__init__()
        self.model_path = model_path
        self.conf = conf
        self.classes = list(classes) if classes is not None else list(WATCH_CLASSES)
        self.min_interval = min_interval
        self.model = None
        self._busy = False
        self._last_submit = 0.0
        self._lock = threading.Lock()
        self._infer_requested.connect(self.process, Qt.ConnectionType.QueuedConnection)

    def load(self) -> None:
        """Загружает модель (вызывается в потоке детектора)."""
        try:
            from core.runtime import configure_process

            configure_process()
            from ultralytics import YOLO

            model = YOLO(self.model_path)
            warmup = model(
                np.zeros((64, 64, 3), dtype=np.uint8),
                conf=self.conf,
                classes=self.classes,
                verbose=False,
            )
            del warmup
            with self._lock:
                self.model = model
            logger.info(f"YOLO загружен: {self.model_path}")
            self.ready.emit()
        except Exception as exc:
            logger.exception("Ошибка загрузки YOLO")
            self.error.emit(f"YOLO load error: {exc}")

    @pyqtSlot(float)
    def set_confidence(self, value: float) -> None:
        self.conf = float(value)

    def submit(self, frame: np.ndarray) -> None:
        """Принимает кадр из потока камеры и ставит в очередь только если детектор свободен."""
        if frame is None or getattr(frame, "size", 0) == 0:
            return

        now = time.monotonic()
        with self._lock:
            if self.model is None or self._busy:
                return
            if now - self._last_submit < self.min_interval:
                return
            self._busy = True
            self._last_submit = now

        self._infer_requested.emit(np.array(frame, dtype=np.uint8, copy=True, order="C"))

    @pyqtSlot(object)
    def process(self, frame: np.ndarray) -> None:
        """Ищет людей (class 0 = person) на кадре."""
        try:
            with self._lock:
                model = self.model
            if model is None:
                return

            owned = np.array(frame, dtype=np.uint8, copy=True, order="C")
            results = model(
                owned,
                conf=self.conf,
                classes=self.classes,
                verbose=False,
            )
            boxes = []
            for result in results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int).tolist()
                    conf = float(box.conf[0])
                    kind = detection_kind(int(box.cls[0]))
                    boxes.append((x1, y1, x2, y2, conf, kind))
            self.detections_ready.emit(boxes)
        except Exception as exc:
            logger.exception("Ошибка детекции")
            self.error.emit(str(exc))
        finally:
            with self._lock:
                self._busy = False
