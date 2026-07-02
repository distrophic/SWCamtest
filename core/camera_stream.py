from __future__ import annotations

import time
from typing import Optional

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from config import CameraDefaults
from utils.logger import get_logger

log = get_logger(__name__)


# =====================================================================
#                            ПОТОК КАМЕРЫ
# =====================================================================
class CameraStream(QThread):
    """Фоновый поток чтения кадров с веб-камеры."""

    frame_ready = pyqtSignal(np.ndarray)
    error       = pyqtSignal(str)
    fps_updated = pyqtSignal(float)
    status      = pyqtSignal(str)

    # -----------------------------------------------------------------
    def __init__(self, config: Optional[CameraDefaults] = None) -> None:
        super().__init__()
        self.config = config or CameraDefaults()
        self._running = False
        self._cap = None

        self._frame_count = 0
        self._fps_timer = time.time()

    # -----------------------------------------------------------------
    #                          ПУБЛИЧНОЕ API
    # -----------------------------------------------------------------
    def stop(self) -> None:
        """Корректно остановить поток."""
        log.info("Останавливаем поток камеры…")
        self._running = False
        self.wait(3000)

    # -----------------------------------------------------------------
    #                          ВНУТРЕННЕЕ
    # -----------------------------------------------------------------
    def _open_camera(self) -> bool:
        """Открывает камеру и применяет настройки."""
        log.info(f"Открываем камеру: {self.config.source}")

        backend = (
            cv2.CAP_V4L2 if isinstance(self.config.source, int) else cv2.CAP_ANY
        )
        self._cap = cv2.VideoCapture(self.config.source, backend)

        if not self._cap.isOpened():
            log.error(f"Не удалось открыть камеру {self.config.source}")
            return False

        if isinstance(self.config.source, int):
            self._cap.set(
                cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG")
            )

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.config.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self._cap.set(cv2.CAP_PROP_FPS,          self.config.fps)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)

        real_w   = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        real_h   = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        real_fps = self._cap.get(cv2.CAP_PROP_FPS)

        fourcc_int = int(self._cap.get(cv2.CAP_PROP_FOURCC))
        fourcc_str = "".join(
            chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)
        )

        log.info(
            f"Камера открыта: {real_w}x{real_h} @ {real_fps:.0f} FPS "
            f"[формат: {fourcc_str}]"
        )

        self.status.emit(f"Камера подключена: {real_w}x{real_h}")
        return True

    # -----------------------------------------------------------------
    def _release_camera(self) -> None:
        """Освобождает камеру."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self.status.emit("Камера отключена")

    # -----------------------------------------------------------------
    def _update_fps(self) -> None:
        """Считает реальный FPS — раз в секунду эмитит сигнал."""
        self._frame_count += 1
        elapsed = time.time() - self._fps_timer
        if elapsed >= 1.0:
            fps = self._frame_count / elapsed
            self.fps_updated.emit(fps)
            self._frame_count = 0
            self._fps_timer   = time.time()

    # -----------------------------------------------------------------
    def run(self) -> None:
        """Главный цикл потока."""
        self._running = True
        attempts = 0

        while self._running:
            if not self._open_camera():
                attempts += 1
                msg = (
                    f"Попытка переподключения "
                    f"{attempts}/{self.config.max_reconnect_attempts}"
                )
                log.warning(msg)
                self.error.emit(msg)

                if attempts >= self.config.max_reconnect_attempts:
                    self.error.emit(
                        "Камера недоступна. Превышен лимит попыток."
                    )
                    break

                time.sleep(self.config.reconnect_delay)
                continue

            attempts = 0

            # --- цикл чтения кадров ---
            while self._running:
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    log.warning("Не удалось прочитать кадр — переподключение…")
                    self._release_camera()
                    break

                self.frame_ready.emit(frame)
                self._update_fps()

        # --- завершение потока ---
        self._release_camera()
        log.info("Поток камеры остановлен.")