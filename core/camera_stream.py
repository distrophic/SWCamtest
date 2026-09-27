from __future__ import annotations

import sys
import time
from typing import Optional

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from config import CameraDefaults
from core.cv_lock import OPENCV
from core.simulator import is_simulator, resolve_source

cv2.setNumThreads(1)
from utils.logger import get_logger

log = get_logger(__name__)


def capture_backends(source: int | str) -> list[int]:
    """Бэкенды OpenCV для источника: Windows DSHOW/MSMF, Linux V4L2, иначе CAP_ANY."""
    if isinstance(source, str) and source.strip().isdigit():
        source = int(source.strip())

    if not isinstance(source, int):
        return [cv2.CAP_ANY]

    if sys.platform == "win32":
        # MSMF на 720p отдаёт ~30 кадров, DSHOW в YUY2 часто залипает на 10.
        preferred = (cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY)
    elif sys.platform.startswith("linux"):
        preferred = (getattr(cv2, "CAP_V4L2", cv2.CAP_ANY), cv2.CAP_ANY)
    elif sys.platform == "darwin":
        preferred = (getattr(cv2, "CAP_AVFOUNDATION", cv2.CAP_ANY), cv2.CAP_ANY)
    else:
        preferred = (cv2.CAP_ANY,)

    unique: list[int] = []
    for backend in preferred:
        if backend not in unique:
            unique.append(backend)
    return unique


def _is_synthetic(source: int | str) -> bool:
    return isinstance(source, str) and source.strip().lower() == "synthetic"


def _is_network(source: int | str) -> bool:
    return isinstance(source, str) and source.strip().lower().startswith(
        ("rtsp://", "http://", "https://")
    )


def _is_local_file(source: int | str) -> bool:
    if is_simulator(source):
        return True
    return isinstance(source, str) and not _is_synthetic(source) and not _is_network(source)


def _fourcc_text(value: int) -> str:
    # Media Foundation отдаёт D3DFMT, а не буквенный FOURCC. 22 — это RGB32.
    known = {20: "RGB24", 21: "ARGB32", 22: "RGB32"}
    if value in known:
        return known[value]
    chars = []
    for shift in range(4):
        byte = (value >> (8 * shift)) & 0xFF
        if 32 <= byte < 127:
            chars.append(chr(byte))
        else:
            return f"0x{value & 0xFFFFFFFF:08X}"
    return "".join(chars) or "?"


def _backend_name(backend: int) -> str:
    get_name = getattr(cv2.videoio_registry, "getBackendName", None)
    if get_name is None:
        return str(backend)
    try:
        return str(get_name(backend))
    except Exception:
        return str(backend)


def _delivery_fps(cap: cv2.VideoCapture, sample_s: float = 0.45) -> float:
    """Сколько кадров read() реально успевает за sample_s. Свойство FPS врёт."""
    try:
        for _ in range(2):
            cap.read()
        started = time.perf_counter()
        count = 0
        while time.perf_counter() - started < sample_s:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            count += 1
        elapsed = time.perf_counter() - started
    except Exception:
        log.exception("Не удалось замерить FPS камеры")
        return 0.0
    if elapsed <= 0 or count == 0:
        return 0.0
    return count / elapsed


def _owned_bgr(frame: np.ndarray) -> np.ndarray | None:
    """Свой непрерывный BGR-кадр, не ссылка на буфер драйвера."""
    if frame.ndim == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    elif frame.ndim != 3:
        return None
    elif frame.shape[2] == 4:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    elif frame.shape[2] != 3:
        return None
    # ascontiguousarray не копирует уже непрерывный кадр, а OpenCV
    # на Windows как раз отдаёт такой вид в свой буфер.
    return np.array(frame, dtype=np.uint8, copy=True, order="C")


class CameraStream(QThread):
    """Фоновый поток чтения кадров с веб-камеры, файла или синтетического источника."""

    frame_ready = pyqtSignal(object)
    error = pyqtSignal(str)
    fps_updated = pyqtSignal(float)
    status = pyqtSignal(str)

    def __init__(self, config: Optional[CameraDefaults] = None) -> None:
        super().__init__()
        self.config = config or CameraDefaults()
        self._running = False
        self._cap = None
        self._synthetic = False
        self._attempts = 0

        self._frame_count = 0
        self._fps_timer = time.time()
        self._synthetic_tick = 0
        self._paused = False
        self._pace_fps = float(self.config.fps)

    def set_paused(self, paused: bool) -> None:
        """Не читает следующий кадр, пока пауза включена. Позиция файла сохраняется."""
        self._paused = bool(paused)

    def stop(self) -> None:
        """Корректно остановить поток. Ожидание короткое: паузы в цикле прерываемые."""
        log.info("Останавливаем поток камеры…")
        self._running = False
        if not self.wait(1500):
            log.warning("Поток камеры не завершился за 1.5 с")

    def _sleep_interruptible(self, seconds: float) -> None:
        if seconds <= 0:
            return
        deadline = time.monotonic() + seconds
        while self._running and time.monotonic() < deadline:
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

    def _needs_pacing(self) -> bool:
        """Файл и synthetic отдают кадры мгновенно — ограничиваем частоту."""
        return self._synthetic or _is_local_file(self.config.source)

    def _open_camera(self) -> bool:
        """Открывает источник и применяет настройки."""
        log.info(f"Открываем камеру: {self.config.source}")

        if _is_synthetic(self.config.source):
            self._synthetic = True
            self._cap = None
            self.status.emit(
                f"Камера подключена: synthetic {self.config.width}x{self.config.height}"
            )
            return True

        self._synthetic = False
        best = None
        best_fps = -1.0
        best_backend: int | None = None
        target = max(float(self.config.fps), 1.0)
        # Файл и сеть: первый живой бэкенд. Веб-камера на Windows: DSHOW часто
        # открывается, но 720p YUY2 реально идёт на 10 FPS, а MSMF — на 30.
        # Берём тот, который быстрее отдаёт кадры, а не тот, который просто открылся.
        pick_by_rate = isinstance(self.config.source, int)
        open_source = resolve_source(self.config.source)
        for backend in capture_backends(self.config.source):
            try:
                cap = cv2.VideoCapture(open_source, backend)
            except Exception:
                log.exception(f"VideoCapture не создался, backend={backend}")
                continue

            if not cap.isOpened():
                cap.release()
                continue

            self._cap = cap
            self._apply_capture_props()
            if not pick_by_rate:
                self._log_opened(backend, None)
                return True

            fps = _delivery_fps(cap)
            name = _backend_name(backend)
            log.info(f"Бэкенд {name}: {fps:.1f} FPS")
            if best is None or fps > best_fps + 1.0:
                if best is not None:
                    best.release()
                best = cap
                best_fps = fps
                best_backend = backend
            else:
                cap.release()
            if best_fps >= target * 0.75:
                break

        if best is None:
            self._cap = None
            log.error(f"Не удалось открыть камеру {self.config.source}")
            return False

        self._cap = best
        if sys.platform == "win32" and best_backend == cv2.CAP_MSMF:
            best.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._log_opened(best_backend, best_fps)
        return True

    def _apply_capture_props(self) -> None:
        if self._cap is None:
            return

        # На Windows DSHOW/MSMF принудительный MJPG и BUFFERSIZE=1
        # после открытия часто роняют драйвер через несколько кадров.
        # На Linux V4L2 MJPG снижает нагрузку на USB.
        file_source = _is_local_file(self.config.source)
        if not file_source:
            if isinstance(self.config.source, int) and not sys.platform.startswith("win"):
                self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
            self._cap.set(cv2.CAP_PROP_FPS, self.config.fps)
            if not sys.platform.startswith("win"):
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        real_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        real_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        real_fps = self._cap.get(cv2.CAP_PROP_FPS)
        if file_source and real_fps and real_fps > 1:
            self._pace_fps = float(real_fps)

        fourcc_int = int(self._cap.get(cv2.CAP_PROP_FOURCC))
        fourcc_str = _fourcc_text(fourcc_int)

        self._opened_desc = (real_w, real_h, real_fps, fourcc_str)

    def _log_opened(self, backend: int | None, measured_fps: float | None) -> None:
        real_w, real_h, real_fps, fourcc_str = getattr(
            self, "_opened_desc", (0, 0, 0.0, "?")
        )
        rate = measured_fps if measured_fps is not None else real_fps
        name = _backend_name(backend) if backend is not None else ""
        suffix = f" [{name}]" if name else ""
        log.info(
            f"Камера открыта: {real_w}x{real_h} @ {rate:.0f} FPS "
            f"[формат: {fourcc_str}]{suffix}"
        )
        self.status.emit(f"Камера подключена: {real_w}x{real_h}")

    def _release_camera(self) -> None:
        """Освобождает камеру."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._synthetic = False
        self.status.emit("Камера отключена")

    def _read_frame(self) -> tuple[bool, np.ndarray | None]:
        if self._synthetic:
            return True, self._synthetic_frame()
        if self._cap is None:
            return False, None
        with OPENCV:
            ok, frame = self._cap.read()
            if not ok or frame is None:
                return False, None
            # Буфер кадра принадлежит VideoCapture и на Windows перезаписывается
            # следующим read(). Копия нужна до отпускания замка.
            return True, _owned_bgr(frame)

    def _synthetic_frame(self) -> np.ndarray:
        height = max(int(self.config.height), 1)
        width = max(int(self.config.width), 1)
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :] = (32, 32, 32)
        box_w = max(width // 8, 4)
        x = int((self._synthetic_tick * max(box_w // 2, 1)) % max(width - box_w, 1))
        y0 = height // 3
        y1 = min(height - 1, y0 + max(height // 4, 4))
        cv2.rectangle(frame, (x, y0), (x + box_w, y1), (0, 180, 0), -1)
        self._synthetic_tick += 1
        return frame

    def _update_fps(self) -> None:
        """Считает реальный FPS — раз в секунду эмитит сигнал."""
        self._frame_count += 1
        elapsed = time.time() - self._fps_timer
        if elapsed >= 1.0:
            fps = self._frame_count / elapsed
            self.fps_updated.emit(fps)
            self._frame_count = 0
            self._fps_timer = time.time()

    def _note_failure(self) -> bool:
        """Считает неудачную попытку. False — лимит исчерпан или поток останавливают."""
        self._attempts += 1
        msg = (
            f"Попытка переподключения "
            f"{self._attempts}/{self.config.max_reconnect_attempts}"
        )
        log.warning(msg)
        self.error.emit(msg)

        if self._attempts >= self.config.max_reconnect_attempts:
            self.error.emit("Камера недоступна. Превышен лимит попыток.")
            return False

        self._sleep_interruptible(self.config.reconnect_delay)
        return self._running

    def _read_loop(self) -> bool:
        """Читает кадры. True — источник оборвался и внешний цикл может переподключиться."""
        self._frame_count = 0
        self._fps_timer = time.time()
        while self._running:
            if self._paused:
                self._sleep_interruptible(0.05)
                continue
            try:
                ok, frame = self._read_frame()
            except Exception:
                log.exception("Ошибка чтения кадра")
                self.error.emit("Ошибка чтения кадра")
                self._release_camera()
                return True

            if not ok or frame is None:
                log.warning("Не удалось прочитать кадр — переподключение…")
                self._release_camera()
                return True

            self.frame_ready.emit(frame)
            self._update_fps()
            if self._needs_pacing():
                self._sleep_interruptible(1.0 / max(float(self._pace_fps), 1.0))
        return False

    def run(self) -> None:
        """Главный цикл потока."""
        self._running = True
        self._attempts = 0

        try:
            while self._running:
                if not self._open_camera():
                    if not self._note_failure():
                        break
                    continue

                self._attempts = 0
                dropped = self._read_loop()
                if not dropped or not self._running:
                    break
                if _is_local_file(self.config.source):
                    continue
                if not self._note_failure():
                    break
        except Exception as exc:
            log.exception("Поток камеры завершился с ошибкой")
            self.error.emit(str(exc))
        finally:
            self._release_camera()
            log.info("Поток камеры остановлен.")
