"""
Recorder — запись видео.

Два режима работы (можно комбинировать):
- Ручной: включается/выключается методами start_manual() / stop_manual().
- Авто: пишет когда детектор находит людей + POST_RECORD хвост.

По умолчанию оба режима ВЫКЛ.

FPS файла определяется автоматически на основе реального темпа кадров,
чтобы избежать эффекта ускоренного/замедленного воспроизведения.

Файлы: data/recordings/YYYY-MM-DD/HH-MM-SS.mp4
"""
from __future__ import annotations

import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from utils.logger import get_logger

logger = get_logger(__name__)


class Recorder(QObject):
    """Пишет видео на диск по ручному триггеру или по детекции."""

    recording_started = pyqtSignal(str)
    recording_stopped = pyqtSignal(str)
    error = pyqtSignal(str)

    # ── Настройки ─────────────────────────────────────────────
    POST_RECORD_SECONDS = 5.0
    MAX_CLIP_SECONDS    = 5 * 60
    FOURCC              = "mp4v"
    EXTENSION           = ".mp4"

    # Для замера реального FPS
    FPS_WINDOW = 60         # сколько последних кадров учитываем
    FPS_MIN    = 5.0        # ограничения на всякий случай
    FPS_MAX    = 60.0
    FPS_FALLBACK = 15.0     # если данных мало — используем это

    def __init__(
        self,
        output_dir: str | Path = "data/recordings",
        fps: float = 30.0,   # используется только как первичный fallback
    ) -> None:
        super().__init__()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.default_fps = fps  # запасное значение
        self._frame_times: deque[float] = deque(maxlen=self.FPS_WINDOW)

        self._writer: Optional[cv2.VideoWriter] = None
        self._current_file: Optional[Path] = None
        self._clip_start_ts: float = 0.0
        self._last_detection_ts: float = 0.0

        self._auto_mode: bool = False
        self._manual_recording: bool = False

    # ── Управление ────────────────────────────────────────────
    @pyqtSlot(bool)
    def set_auto_mode(self, enabled: bool) -> None:
        self._auto_mode = bool(enabled)
        logger.info(f"Авто-запись: {'ВКЛ' if enabled else 'ВЫКЛ'}")
        if not enabled and not self._manual_recording:
            self._last_detection_ts = 0.0

    @pyqtSlot()
    def start_manual(self) -> None:
        if self._manual_recording:
            return
        self._manual_recording = True
        logger.info("Ручная запись: НАЧАТА")

    @pyqtSlot()
    def stop_manual(self) -> None:
        if not self._manual_recording:
            return
        self._manual_recording = False
        logger.info("Ручная запись: ОСТАНОВЛЕНА")

    @pyqtSlot()
    def toggle_manual(self) -> None:
        if self._manual_recording:
            self.stop_manual()
        else:
            self.start_manual()

    def stop(self) -> None:
        self._manual_recording = False
        self._auto_mode = False
        if self._writer is not None:
            self._close_writer()

    # ── Слоты пайплайна ───────────────────────────────────────
    @pyqtSlot(np.ndarray)
    def on_frame(self, frame: np.ndarray) -> None:
        if frame is None or frame.size == 0:
            return

        now = time.time()
        # Всегда обновляем окно замера FPS (даже когда не пишем)
        self._frame_times.append(now)

        should_record = self._should_record(now)

        if self._writer is not None and not should_record:
            self._close_writer()
            return

        if should_record:
            if (
                self._writer is not None
                and (now - self._clip_start_ts) >= self.MAX_CLIP_SECONDS
            ):
                self._close_writer()

            if self._writer is None:
                self._open_writer(frame)

            if self._writer is not None:
                self._writer.write(frame)

    @pyqtSlot(list)
    def on_detections(self, boxes: list) -> None:
        if self._auto_mode and boxes:
            self._last_detection_ts = time.time()

    # ── Внутреннее ────────────────────────────────────────────
    def _should_record(self, now: float) -> bool:
        if self._manual_recording:
            return True
        if self._auto_mode and self._last_detection_ts > 0:
            if (now - self._last_detection_ts) <= self.POST_RECORD_SECONDS:
                return True
        return False

    def _measure_fps(self) -> float:
        """Возвращает реальный FPS на основе последних кадров."""
        if len(self._frame_times) < 10:
            return self.default_fps or self.FPS_FALLBACK

        span = self._frame_times[-1] - self._frame_times[0]
        if span <= 0:
            return self.default_fps or self.FPS_FALLBACK

        fps = (len(self._frame_times) - 1) / span
        # Зажимаем в разумные пределы
        return max(self.FPS_MIN, min(self.FPS_MAX, fps))

    def _open_writer(self, frame: np.ndarray) -> None:
        h, w = frame.shape[:2]
        fps = self._measure_fps()

        now = datetime.now()
        day_dir = self.output_dir / now.strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)

        filename = now.strftime("%H-%M-%S") + self.EXTENSION
        filepath = day_dir / filename

        fourcc = cv2.VideoWriter_fourcc(*self.FOURCC)
        writer = cv2.VideoWriter(str(filepath), fourcc, fps, (w, h))

        if not writer.isOpened():
            msg = f"Не удалось открыть VideoWriter для {filepath}"
            logger.error(msg)
            self.error.emit(msg)
            return

        self._writer = writer
        self._current_file = filepath
        self._clip_start_ts = time.time()

        logger.info(f"🎬 Запись начата: {filepath} @ {fps:.1f} FPS")
        self.recording_started.emit(str(filepath))

    def _close_writer(self) -> None:
        if self._writer is None:
            return
        self._writer.release()
        duration = time.time() - self._clip_start_ts

        path_str = str(self._current_file) if self._current_file else "?"
        logger.info(f"⏹ Запись остановлена: {path_str} ({duration:.1f}s)")
        self.recording_stopped.emit(path_str)

        self._writer = None
        self._current_file = None