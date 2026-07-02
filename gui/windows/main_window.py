"""Главное окно приложения."""

from PyQt6.QtWidgets import (
    QMainWindow, QLabel, QWidget, QVBoxLayout,
    QPushButton, QHBoxLayout, QStatusBar,
)
from PyQt6.QtCore import QThread, Qt
from auth import AuthService, Session
from config import CAMERA
from core.detector import PersonDetector
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

        # ── Атрибуты (инициализируем ЗАРАНЕЕ, чтобы не было AttributeError)
        self.camera: CameraStream | None = None
        self.video_widget: VideoWidget | None = None
        self.detector: PersonDetector | None = None
        self.detector_thread: QThread | None = None

        self._build_ui()
        self._update_status()
        self._start_camera()
        self._start_detector()   # ← ТЕПЕРЬ ВЫЗЫВАЕТСЯ

    # ── UI ─────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # ── Шапка ─────────────────────────────────────────────
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
        """Запускает YOLO-детектор в отдельном потоке."""
        self.detector_thread = QThread()
        self.detector = PersonDetector(conf=0.4)
        self.detector.moveToThread(self.detector_thread)

        # Загружаем модель, как только поток стартанул
        self.detector_thread.started.connect(self.detector.load)

        # Сигналы состояния
        self.detector.ready.connect(self._on_detector_ready)
        self.detector.error.connect(self._on_detector_error)

        # ── Пайплайн детекции ──
        # Камера → detector.process (через очередь между потоками)
        if self.camera is not None:
            self.camera.frame_ready.connect(
                self.detector.process, Qt.ConnectionType.QueuedConnection
            )
        # Детектор → VideoWidget.set_detections (рисует боксы)
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

    # ── Слоты для сигналов ──────────────────────────────
    def _on_fps(self, fps: float) -> None:
        self.fps_label.setText(f"FPS: {fps:5.1f}")

    def _on_status(self, msg: str) -> None:
        """Сообщения от камеры (подключение/отключение/инфо)."""
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

    # ── Прочее ─────────────────────────────────────────────────
    def _update_status(self) -> None:
        user = Session.current_user()
        self.statusBar().showMessage(
            f"Пользователь: {user.username}  •  Роль: {user.role}  •  Статус: онлайн"
        )

    def _on_logout(self) -> None:
        self._stop_detector()
        self._stop_camera()
        AuthService.logout()
        self.close()

    def closeEvent(self, event):  # noqa: N802
        """Корректно останавливаем всё при закрытии окна."""
        self._stop_detector()
        self._stop_camera()
        super().closeEvent(event)