"""Главное окно приложения."""

from PyQt6.QtWidgets import (
    QMainWindow, QLabel, QWidget, QVBoxLayout,
    QPushButton, QHBoxLayout, QStatusBar, QCheckBox,
)
from PyQt6.QtCore import QThread, Qt
from auth import AuthService, Session
from config import CAMERA
from core.detector import PersonDetector
from core.recorder import Recorder
from core.camera_stream import CameraStream
from gui.widgets.video_widget import VideoWidget
from utils.logger import get_logger

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Главное окно после успешного входа."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SecureWatch")
        self.resize(1100, 700)

        # ── Атрибуты ──────────────────────────────────────────
        self.camera: CameraStream | None = None
        self.video_widget: VideoWidget | None = None
        self.detector: PersonDetector | None = None
        self.detector_thread: QThread | None = None
        self.recorder: Recorder | None = None
        self.recorder_thread: QThread | None = None

        self._build_ui()
        self._update_status()
        self._start_camera()
        self._start_detector()
        self._start_recorder()

    # ── UI ─────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # ── Верхняя шапка ─────────────────────────────────────
        header = QHBoxLayout()
        user = Session.current_user()
        greeting = QLabel(
            f"👋 Добро пожаловать, <b>{user.username}</b> ({user.role})"
        )
        greeting.setStyleSheet("font-size: 14px;")
        header.addWidget(greeting)
        header.addStretch()

        self.fps_label = QLabel("FPS: —")
        self.fps_label.setStyleSheet("color: #6c6; font-family: monospace;")
        header.addWidget(self.fps_label)

        self.detector_label = QLabel("🧠 —")
        self.detector_label.setStyleSheet("color: #888; font-family: monospace;")
        header.addWidget(self.detector_label)

        self.rec_label = QLabel("⚫ idle")
        self.rec_label.setStyleSheet("color: #888; font-family: monospace;")
        header.addWidget(self.rec_label)

        self.connection_label = QLabel("● offline")
        self.connection_label.setStyleSheet("color: #c66; font-weight: bold;")
        header.addWidget(self.connection_label)

        self.logout_btn = QPushButton("Выйти")
        self.logout_btn.clicked.connect(self._on_logout)
        header.addWidget(self.logout_btn)

        layout.addLayout(header)

        # ── Видео ─────────────────────────────────────────────
        self.video_widget = VideoWidget()
        layout.addWidget(self.video_widget, stretch=1)

        # ── Панель управления записью ─────────────────────────
        controls = QHBoxLayout()

        self.rec_btn = QPushButton("🔴 Начать запись")
        self.rec_btn.setCheckable(True)
        self.rec_btn.setMinimumWidth(180)
        self.rec_btn.setStyleSheet(
            "QPushButton { padding: 8px 16px; font-weight: bold; }"
            "QPushButton:checked { background-color: #c33; color: white; }"
        )
        self.rec_btn.toggled.connect(self._on_rec_btn_toggled)
        controls.addWidget(self.rec_btn)

        self.auto_checkbox = QCheckBox("Авто-запись по детекции")
        self.auto_checkbox.setStyleSheet("padding: 4px;")
        self.auto_checkbox.toggled.connect(self._on_auto_toggled)
        controls.addWidget(self.auto_checkbox)

        controls.addStretch()
        layout.addLayout(controls)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

    # ── Камера ─────────────────────────────────────────────────
    def _start_camera(self) -> None:
        self.camera = CameraStream(CAMERA)

        self.camera.frame_ready.connect(self.video_widget.update_frame)
        self.camera.fps_updated.connect(self._on_fps)
        self.camera.status.connect(self._on_status)
        self.camera.error.connect(self._on_camera_error)

        self.camera.start()
        logger.info("Поток камеры запущен.")

    def _stop_camera(self) -> None:
        if self.camera is not None:
            self.camera.stop()
            self.camera = None

    # ── Детектор ───────────────────────────────────────────────
    def _start_detector(self) -> None:
        self.detector_thread = QThread()
        self.detector = PersonDetector(conf=0.4)
        self.detector.moveToThread(self.detector_thread)

        self.detector_thread.started.connect(self.detector.load)
        self.detector.ready.connect(self._on_detector_ready)
        self.detector.error.connect(self._on_detector_error)

        if self.camera is not None:
            self.camera.frame_ready.connect(
                self.detector.process, Qt.ConnectionType.QueuedConnection
            )
        self.detector.detections_ready.connect(self.video_widget.set_detections)

        self.detector_thread.start()
        logger.info("Поток детектора запущен.")

    def _stop_detector(self) -> None:
        if self.detector_thread is not None:
            self.detector_thread.quit()
            self.detector_thread.wait(2000)
            self.detector_thread = None
            self.detector = None
            logger.info("Поток детектора остановлен.")

    # ── Recorder ───────────────────────────────────────────────
    def _start_recorder(self) -> None:
        self.recorder_thread = QThread()
        self.recorder = Recorder(fps=float(getattr(CAMERA, "fps", 30.0)))
        self.recorder.moveToThread(self.recorder_thread)

        if self.camera is not None:
            self.camera.frame_ready.connect(
                self.recorder.on_frame, Qt.ConnectionType.QueuedConnection
            )

        if self.detector is not None:
            self.detector.detections_ready.connect(
                self.recorder.on_detections, Qt.ConnectionType.QueuedConnection
            )

        self.recorder.recording_started.connect(self._on_recording_started)
        self.recorder.recording_stopped.connect(self._on_recording_stopped)
        self.recorder.error.connect(self._on_camera_error)

        self.recorder_thread.start()
        logger.info("Поток recorder запущен.")

    def _stop_recorder(self) -> None:
        if self.recorder is not None:
            self.recorder.stop()
        if self.recorder_thread is not None:
            self.recorder_thread.quit()
            self.recorder_thread.wait(2000)
            self.recorder_thread = None
            self.recorder = None
            logger.info("Поток recorder остановлен.")

    # ── Слоты для сигналов камеры/детектора ───────────────────
    def _on_fps(self, fps: float) -> None:
        self.fps_label.setText(f"FPS: {fps:5.1f}")

    def _on_status(self, msg: str) -> None:
        logger.info(f"Камера: {msg}")

        if "подключена" in msg.lower():
            self.connection_label.setText("● online")
            self.connection_label.setStyleSheet(
                "color: #6c6; font-weight: bold;"
            )
        elif "отключена" in msg.lower():
            self.connection_label.setText("● offline")
            self.connection_label.setStyleSheet(
                "color: #c66; font-weight: bold;"
            )

        self.statusBar().showMessage(msg, 3000)

    def _on_camera_error(self, msg: str) -> None:
        logger.warning(f"Камера: {msg}")
        self.statusBar().showMessage(f"⚠ {msg}", 5000)

    def _on_detector_ready(self) -> None:
        logger.info("Детектор готов к работе.")
        self.detector_label.setText("🧠 ready")
        self.detector_label.setStyleSheet(
            "color: #6c6; font-family: monospace;"
        )
        self.statusBar().showMessage("✅ Детектор готов", 3000)

    def _on_detector_error(self, msg: str) -> None:
        logger.error(f"Детектор: {msg}")
        self.detector_label.setText("🧠 error")
        self.detector_label.setStyleSheet(
            "color: #c66; font-family: monospace;"
        )
        self.statusBar().showMessage(f"⚠ Детектор: {msg}", 5000)

    # ── Слоты для управления записью ──────────────────────────
    def _on_rec_btn_toggled(self, checked: bool) -> None:
        """Клик по кнопке 'Начать/Остановить запись'."""
        if self.recorder is None:
            return
        if checked:
            self.recorder.start_manual()
            self.rec_btn.setText("⏹ Остановить запись")
        else:
            self.recorder.stop_manual()
            self.rec_btn.setText("🔴 Начать запись")

    def _on_auto_toggled(self, checked: bool) -> None:
        """Клик по чекбоксу 'Авто-запись по детекции'."""
        if self.recorder is None:
            return
        self.recorder.set_auto_mode(checked)
        status = "включена" if checked else "выключена"
        self.statusBar().showMessage(f"Авто-запись {status}", 2000)

    def _on_recording_started(self, path: str) -> None:
        logger.info(f"🔴 REC: {path}")
        self.rec_label.setText("🔴 REC")
        self.rec_label.setStyleSheet(
            "color: #c66; font-family: monospace; font-weight: bold;"
        )
        self.statusBar().showMessage(f"🔴 Запись: {path}", 3000)

    def _on_recording_stopped(self, path: str) -> None:
        logger.info(f"⏹ STOP: {path}")
        self.rec_label.setText("⚫ idle")
        self.rec_label.setStyleSheet("color: #888; font-family: monospace;")
        self.statusBar().showMessage(f"⏹ Сохранено: {path}", 3000)

    # ── Прочее ─────────────────────────────────────────────────
    def _update_status(self) -> None:
        user = Session.current_user()
        self.statusBar().showMessage(
            f"Пользователь: {user.username}  •  Роль: {user.role}  •  Статус: онлайн"
        )

    def _on_logout(self) -> None:
        self._stop_recorder()
        self._stop_detector()
        self._stop_camera()
        AuthService.logout()
        self.close()

    def closeEvent(self, event):  # noqa: N802
        self._stop_recorder()
        self._stop_detector()
        self._stop_camera()
        super().closeEvent(event)