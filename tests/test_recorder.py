"""Запись на временных кадрах, без камеры и без модели."""

import time
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal

from core.recorder import Recorder


def _frame(index: int = 0) -> np.ndarray:
    frame = np.zeros((32, 48, 3), dtype=np.uint8)
    frame[:, :, 0] = index % 255
    return frame


def test_manual_recording_writes_file(tmp_path: Path):
    recorder = Recorder(output_dir=tmp_path, fps=10)
    recorder.start_manual()
    for index in range(3):
        recorder.on_frame(_frame(index))
    recorder.stop()

    files = list(tmp_path.rglob("*.mp4"))
    assert len(files) == 1
    assert files[0].stat().st_size > 0


def test_auto_recording_stops_after_post_roll(tmp_path: Path):
    recorder = Recorder(output_dir=tmp_path, fps=10)
    recorder.POST_RECORD_SECONDS = 0.05
    recorder.set_auto_mode(True)
    recorder.on_detections([(0, 0, 10, 10, 0.9)])
    recorder.on_frame(_frame(1))
    assert recorder._writer is not None

    time.sleep(0.08)
    recorder.on_detections([])
    recorder.on_frame(_frame(2))
    assert recorder._writer is None
    assert list(tmp_path.rglob("*.mp4"))


def test_release_writer_runs_on_recorder_thread(qtbot, tmp_path: Path):
    class Bridge(QObject):
        release = pyqtSignal()

    thread = QThread()
    recorder = Recorder(output_dir=tmp_path, fps=10)
    recorder.moveToThread(thread)
    bridge = Bridge()
    bridge.release.connect(
        recorder.release_writer,
        Qt.ConnectionType.BlockingQueuedConnection,
    )
    seen: list[int] = []

    def _mark_close() -> None:
        seen.append(1)
        recorder._writer = None

    recorder._close_writer = _mark_close
    recorder._writer = object()
    thread.start()
    qtbot.waitUntil(lambda: thread.isRunning(), timeout=2000)
    try:
        bridge.release.emit()
        assert seen == [1]
    finally:
        recorder._writer = None
        thread.quit()
        thread.wait(2000)
