"""
Тест нашего CameraStream — без GUI.
Слушаем сигналы (frame_ready, fps_updated, error_occurred, connection_changed)
и печатаем события в консоль.

Запуск:  python tests/test_camera_stream.py
Выход:   автоматически через 10 секунд (или Ctrl+C)
"""
from __future__ import annotations

import sys

import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from core.camera_stream import CameraConfig, CameraStream


def main() -> None:
    app = QApplication(sys.argv)

    stream = CameraStream(
        CameraConfig(source=0, width=1280, height=720, fps=30)
    )

    # счётчик кадров (внутри dict, чтобы менять из вложенной функции)
    counter: dict[str, int] = {"n": 0}

    def on_frame(frame: np.ndarray) -> None:
        counter["n"] += 1
        # печатаем каждый 30-й кадр, чтобы не засорять консоль
        if counter["n"] % 30 == 0:
            print(f"[FRAME] #{counter['n']:>4}  shape={frame.shape}")

    def on_error(msg: str) -> None:
        print(f"[ERROR] {msg}")

    def on_connection(connected: bool) -> None:
        status = "connected ✅" if connected else "disconnected ❌"
        print(f"[CONN ] {status}")

    def on_fps(fps: float) -> None:
        print(f"[FPS  ] {fps:.1f}")

    # подключаем сигналы
    stream.frame_ready.connect(on_frame)
    stream.error_occurred.connect(on_error)
    stream.connection_changed.connect(on_connection)
    stream.fps_updated.connect(on_fps)

    # автоостановка через 10 секунд
    def shutdown() -> None:
        print("\n--- Тест завершён, останавливаю поток ---")
        stream.stop()
        app.quit()

    QTimer.singleShot(10_000, shutdown)
    app.aboutToQuit.connect(stream.stop)

    print("▶️  Запускаю CameraStream на 10 секунд...\n")
    stream.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()