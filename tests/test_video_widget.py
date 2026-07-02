"""
Тест GUI: открываем окно, показываем живое видео с камеры.

Запуск:  python -m tests.test_video_widget
Выход:   закрыть окно или Ctrl+C
"""
from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from core.camera_stream import CameraConfig, CameraStream
from gui.widgets.video_widget import VideoWidget


class TestWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SecureWatch — тест видео")
        self.resize(960, 600)

        # === виджеты ===
        self.video = VideoWidget()

        self.btn_start = QPushButton("▶ Старт")
        self.btn_stop = QPushButton("⏹ Стоп")
        self.btn_stop.setEnabled(False)

        self.lbl_fps = QLabel("FPS: —")
        self.lbl_fps.setStyleSheet("font-weight: bold;")

        # === разметка ===
        bottom = QHBoxLayout()
        bottom.addWidget(self.btn_start)
        bottom.addWidget(self.btn_stop)
        bottom.addStretch()
        bottom.addWidget(self.lbl_fps)

        root = QVBoxLayout()
        root.addWidget(self.video, stretch=1)
        root.addLayout(bottom)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Готов")

        # === поток камеры ===
        self.stream = CameraStream(
            CameraConfig(source=0, width=1280, height=720, fps=30)
        )
        self.stream.frame_ready.connect(self.video.update_frame)
        self.stream.fps_updated.connect(self._on_fps)
        self.stream.connection_changed.connect(self._on_conn)
        self.stream.error_occurred.connect(self._on_error)

        # === кнопки ===
        self.btn_start.clicked.connect(self._start)
        self.btn_stop.clicked.connect(self._stop)

    # --- слоты ---
    def _start(self) -> None:
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.statusBar().showMessage("Запускаю камеру...")
        self.stream.start()

    def _stop(self) -> None:
        self.stream.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.statusBar().showMessage("Камера остановлена")

    def _on_fps(self, fps: float) -> None:
        self.lbl_fps.setText(f"FPS: {fps:.1f}")

    def _on_conn(self, ok: bool) -> None:
        self.statusBar().showMessage("✅ Подключено" if ok else "❌ Отключено")

    def _on_error(self, msg: str) -> None:
        self.statusBar().showMessage(f"⚠ Ошибка: {msg}")

    # --- закрытие ---
    def closeEvent(self, event) -> None:  # noqa: N802
        self.stream.stop()
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    win = TestWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()