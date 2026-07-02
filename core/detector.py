"""YOLOv8 детектор людей."""

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from ultralytics import YOLO

from utils.logger import get_logger

logger = get_logger(__name__)


class PersonDetector(QObject):
    detections_ready = pyqtSignal(list)
    error = pyqtSignal(str)
    ready = pyqtSignal()

    def __init__(self, model_path: str = "yolov8n.pt", conf: float = 0.4):
        super().__init__()
        self.model_path = model_path
        self.conf = conf
        self.model: YOLO | None = None
        self._busy = False

    def load(self) -> None:
        """Загружает модель (вызывается в потоке детектора)."""
        try:
            self.model = YOLO(self.model_path)
            logger.info(f"YOLO загружен: {self.model_path}")
            self.ready.emit()
        except Exception as e:
            logger.exception("Ошибка загрузки YOLO")
            self.error.emit(f"YOLO load error: {e}")

    def process(self, frame: np.ndarray) -> None:
        """Ищет людей (class 0 = person) на кадре."""
        if self.model is None or self._busy:
            return  # пропускаем кадр, если ещё обрабатываем предыдущий

        self._busy = True
        try:
            results = self.model(
                frame,
                conf=self.conf,
                classes=[0],     # только люди
                verbose=False,
            )
            boxes = []
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    x1, y1, x2, y2 = (
                        box.xyxy[0].cpu().numpy().astype(int).tolist()
                    )
                    conf = float(box.conf[0])
                    boxes.append((x1, y1, x2, y2, conf))
            self.detections_ready.emit(boxes)
        except Exception as e:
            logger.exception("Ошибка детекции")
            self.error.emit(str(e))
        finally:
            self._busy = False