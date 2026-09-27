"""Жизненный цикл камеры, детектора и записи. Живёт в GUI-потоке."""

from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal

from config import CAMERA, DETECTOR, RECORDINGS_DIR
from core.camera_stream import CameraStream
from core.recorder import Recorder
from core.detections import persons_only
from core.zone import Zone, people_in_zone
from utils.logger import get_logger

logger = get_logger(__name__)


class Pipeline(QObject):
    """Старт, смена источника и остановка трёх потоков."""

    frame_ready = pyqtSignal(object)
    fps_updated = pyqtSignal(float)
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    detector_ready = pyqtSignal()
    detector_failed = pyqtSignal(str)
    detections_ready = pyqtSignal(list)
    persons_ready = pyqtSignal(list)
    recording_started = pyqtSignal(str)
    recording_stopped = pyqtSignal(str)
    camera_available = pyqtSignal(bool)

    _sig_start_manual = pyqtSignal()
    _sig_stop_manual = pyqtSignal()
    _sig_auto_mode = pyqtSignal(bool)
    _sig_stop_recorder = pyqtSignal()
    _sig_release_writer = pyqtSignal()
    _sig_set_confidence = pyqtSignal(float)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._camera: CameraStream | None = None
        self._detector = None
        self._detector_thread: QThread | None = None
        self._recorder: Recorder | None = None
        self._recorder_thread: QThread | None = None
        self._stopped = True
        self._camera_up = False
        self._source: int | str = CAMERA.source
        self._zone: Zone | None = None
        self._frame_hw: tuple[int, int] = (0, 0)

    @property
    def camera_up(self) -> bool:
        return self._camera_up

    def is_running(self) -> bool:
        return not self._stopped

    def start(
        self,
        source: int | str,
        confidence: float,
        *,
        with_detector: bool = True,
        open_camera: bool = True,
    ) -> None:
        """Поднимает потоки. Ошибка детектора не прерывает камеру и запись."""
        self._stopped = False
        self._camera_up = False
        self._source = source
        if with_detector and not self._preload_inference():
            with_detector = False
        if open_camera:
            self._start_camera(source)
        if with_detector:
            self._start_detector(confidence)
        self._start_recorder()

    def _preload_inference(self) -> bool:
        """True, если YOLO уже импортирован и камеру можно открывать."""
        try:
            from core.runtime import preload_inference

            preload_inference()
            return True
        except Exception as exc:
            logger.exception("Детектор не загружается")
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(0, lambda: self.detector_failed.emit(str(exc)))
            return False

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._stop_recorder()
        self._stop_detector()
        self._stop_camera()

    def set_source(self, source: int | str) -> None:
        self._close_open_clip()
        self._source = source
        self._camera_up = False
        self.camera_available.emit(False)
        self._start_camera(source)

    def blank(self) -> None:
        """Останавливает картинку выбранной ячейки, детектор и запись остаются."""
        self._close_open_clip()
        self._stop_camera()
        self._camera_up = False
        self.camera_available.emit(False)

    def set_paused(self, paused: bool) -> None:
        if self._camera is not None:
            self._camera.set_paused(paused)

    def set_zone(self, zone: Zone | None) -> None:
        self._zone = zone

    def set_confidence(self, value: float) -> None:
        self._sig_set_confidence.emit(float(value))

    def request_manual(self, enabled: bool) -> bool:
        """False, если запись включить нельзя: камера ещё не дала кадр."""
        if enabled and not self._camera_up:
            self.error.emit("Камера недоступна. Запись не начата.")
            return False
        if self._recorder is None:
            return False
        if enabled:
            self._sig_start_manual.emit()
        else:
            self._sig_stop_manual.emit()
        return True

    def set_auto_mode(self, enabled: bool) -> bool:
        if enabled and not self._camera_up:
            self.error.emit("Камера недоступна. Авто-запись не включена.")
            return False
        if self._recorder is None:
            return False
        self._sig_auto_mode.emit(bool(enabled))
        return True

    def camera_config(self, source: int | str):
        return self._camera_config(source)

    def _camera_config(self, source: int | str):
        if source == CAMERA.source:
            return CAMERA
        return type(CAMERA)(
            source=source,
            width=CAMERA.width,
            height=CAMERA.height,
            fps=CAMERA.fps,
            max_reconnect_attempts=CAMERA.max_reconnect_attempts,
            reconnect_delay=CAMERA.reconnect_delay,
        )

    def _start_camera(self, source: int | str) -> None:
        self._stop_camera()
        self._camera = CameraStream(self._camera_config(source))
        self._camera.frame_ready.connect(self._note_frame)
        self._camera.frame_ready.connect(self.frame_ready)
        self._camera.fps_updated.connect(self.fps_updated)
        self._camera.status.connect(self._on_status)
        self._camera.error.connect(self._on_error)
        if self._detector is not None:
            self._camera.frame_ready.connect(
                self._detector.submit, Qt.ConnectionType.DirectConnection
            )
        if self._recorder is not None:
            self._camera.frame_ready.connect(
                self._recorder.on_frame, Qt.ConnectionType.QueuedConnection
            )
        self._camera.start()
        self._stopped = False
        logger.info("Поток камеры запущен.")

    def _stop_camera(self) -> None:
        if self._camera is not None:
            self._camera.stop()
            self._camera = None

    def _start_detector(self, confidence: float) -> None:
        try:
            from core.detector import PersonDetector
        except Exception as exc:
            logger.exception("Детектор не импортируется")
            self.detector_failed.emit(str(exc))
            return

        self._detector_thread = QThread()
        self._detector = PersonDetector(
            model_path=DETECTOR.model_path,
            conf=float(confidence),
            classes=list(DETECTOR.classes),
            min_interval=float(DETECTOR.min_interval),
        )
        self._detector.moveToThread(self._detector_thread)
        self._detector_thread.started.connect(self._detector.load)
        self._detector.ready.connect(self.detector_ready)
        self._detector.error.connect(self.detector_failed)
        self._detector.detections_ready.connect(self._filter_detections)
        self._sig_set_confidence.connect(
            self._detector.set_confidence, Qt.ConnectionType.QueuedConnection
        )
        if self._camera is not None:
            self._camera.frame_ready.connect(
                self._detector.submit, Qt.ConnectionType.DirectConnection
            )
        self._detector_thread.start()
        logger.info("Поток детектора запущен.")

    def _stop_detector(self) -> None:
        if self._detector_thread is not None:
            self._detector_thread.quit()
            self._detector_thread.wait(2000)
            self._detector_thread = None
            self._detector = None
            logger.info("Поток детектора остановлен.")

    def _start_recorder(self) -> None:
        self._recorder_thread = QThread()
        self._recorder = Recorder(
            output_dir=RECORDINGS_DIR,
            fps=float(getattr(CAMERA, "fps", 30.0)),
        )
        self._recorder.moveToThread(self._recorder_thread)
        self._sig_start_manual.connect(
            self._recorder.start_manual, Qt.ConnectionType.QueuedConnection
        )
        self._sig_stop_manual.connect(
            self._recorder.stop_manual, Qt.ConnectionType.QueuedConnection
        )
        self._sig_auto_mode.connect(
            self._recorder.set_auto_mode, Qt.ConnectionType.QueuedConnection
        )
        self._sig_stop_recorder.connect(
            self._recorder.stop, Qt.ConnectionType.QueuedConnection
        )
        self._sig_release_writer.connect(
            self._recorder.release_writer,
            Qt.ConnectionType.BlockingQueuedConnection,
        )
        if self._camera is not None:
            self._camera.frame_ready.connect(
                self._recorder.on_frame, Qt.ConnectionType.QueuedConnection
            )
        self.persons_ready.connect(
            self._recorder.on_detections, Qt.ConnectionType.QueuedConnection
        )
        self._recorder.recording_started.connect(self.recording_started)
        self._recorder.recording_stopped.connect(self.recording_stopped)
        self._recorder.error.connect(self._on_error)
        self._recorder_thread.start()
        logger.info("Поток recorder запущен.")

    def _stop_recorder(self) -> None:
        if self._recorder_thread is not None and self._recorder_thread.isRunning():
            self._sig_stop_recorder.emit()
            self._recorder_thread.quit()
            self._recorder_thread.wait(2000)
        self._recorder_thread = None
        self._recorder = None

    def _close_open_clip(self) -> None:
        if self._recorder is None or self._recorder_thread is None:
            return
        if not self._recorder_thread.isRunning():
            return
        self._sig_release_writer.emit()

    def _note_frame(self, frame: object) -> None:
        shape = getattr(frame, "shape", None)
        if shape is not None and len(shape) >= 2:
            self._frame_hw = (int(shape[0]), int(shape[1]))

    def _filter_detections(self, boxes: list) -> None:
        height, width = self._frame_hw
        visible = people_in_zone(boxes, self._zone, height, width)
        self.detections_ready.emit(visible)
        self.persons_ready.emit(persons_only(visible))

    def _on_status(self, msg: str) -> None:
        if "подключена" in msg.lower():
            self._camera_up = True
            self.camera_available.emit(True)
        self.status.emit(msg)

    def _on_error(self, msg: str) -> None:
        self.error.emit(msg)
        if "Превышен лимит" in msg:
            self._camera_up = False
            self.camera_available.emit(False)
            self._sig_stop_manual.emit()
            self._sig_auto_mode.emit(False)
