"""Поток камеры без реального устройства."""

import cv2
import numpy as np
import pytest

from config import CameraDefaults
from core.camera_stream import CameraStream, _owned_bgr, capture_backends


def test_owned_bgr_does_not_alias_driver_buffer():
    source = np.zeros((8, 8, 3), dtype=np.uint8)
    owned = _owned_bgr(source)
    assert owned is not None
    assert owned.flags["C_CONTIGUOUS"]
    owned[0, 0, 0] = 9
    assert source[0, 0, 0] == 0


def test_windows_backends(monkeypatch):
    monkeypatch.setattr("core.camera_stream.sys.platform", "win32")
    backends = capture_backends(0)
    assert backends[0] == cv2.CAP_MSMF
    assert cv2.CAP_DSHOW in backends
    assert cv2.CAP_ANY in backends


def test_linux_backends(monkeypatch):
    monkeypatch.setattr("core.camera_stream.sys.platform", "linux")
    backends = capture_backends(0)
    assert backends[0] == cv2.CAP_V4L2


def test_url_uses_any_backend():
    assert capture_backends("rtsp://example.com/stream") == [cv2.CAP_ANY]


def test_simulator_plays_demo_clip(qtbot):
    stream = CameraStream(CameraDefaults(source="simulator", width=320, height=240, fps=10))
    frames: list = []
    stream.frame_ready.connect(frames.append)
    stream.start()
    try:
        qtbot.waitUntil(lambda: len(frames) >= 1, timeout=4000)
    finally:
        stream.stop()
    assert frames[0].ndim == 3
    assert frames[0].shape[1] == 320


def test_synthetic_emits_frame(qtbot):
    stream = CameraStream(
        CameraDefaults(source="synthetic", width=32, height=24, fps=20)
    )
    frames = []
    stream.frame_ready.connect(frames.append)
    stream.start()
    try:
        qtbot.waitUntil(lambda: len(frames) >= 1, timeout=3000)
    finally:
        stream.stop()
    assert frames[0].shape == (24, 32, 3)


def test_pause_holds_synthetic_frames(qtbot):
    stream = CameraStream(
        CameraDefaults(source="synthetic", width=32, height=24, fps=20)
    )
    frames: list = []
    stream.frame_ready.connect(frames.append)
    stream.start()
    try:
        qtbot.waitUntil(lambda: len(frames) >= 1, timeout=3000)
        stream.set_paused(True)
        held = len(frames)
        qtbot.wait(250)
        assert len(frames) == held
        stream.set_paused(False)
        qtbot.waitUntil(lambda: len(frames) > held, timeout=2000)
    finally:
        stream.stop()


def test_gives_up_when_camera_missing(qtbot, monkeypatch):
    class Closed:
        def isOpened(self):
            return False

        def release(self):
            return None

    monkeypatch.setattr(cv2, "VideoCapture", lambda *args, **kwargs: Closed())
    stream = CameraStream(
        CameraDefaults(source=0, max_reconnect_attempts=2, reconnect_delay=0.05)
    )
    errors: list[str] = []
    stream.error.connect(errors.append)
    stream.start()
    try:
        qtbot.waitUntil(lambda: not stream.isRunning(), timeout=4000)
    finally:
        stream.stop()
    assert any("Превышен лимит" in msg for msg in errors)


def test_releases_capture_when_read_fails(qtbot, monkeypatch):
    state = {"released": 0}

    class Cap:
        def isOpened(self):
            return True

        def set(self, *args):
            return True

        def get(self, prop):
            if prop == cv2.CAP_PROP_FRAME_WIDTH:
                return 32
            if prop == cv2.CAP_PROP_FRAME_HEIGHT:
                return 24
            if prop == cv2.CAP_PROP_FPS:
                return 10
            return 0

        def read(self):
            raise RuntimeError("boom")

        def release(self):
            state["released"] += 1

    monkeypatch.setattr(cv2, "VideoCapture", lambda *args, **kwargs: Cap())
    stream = CameraStream(
        CameraDefaults(
            source=0,
            width=32,
            height=24,
            fps=10,
            max_reconnect_attempts=1,
            reconnect_delay=0.01,
        )
    )
    stream.start()
    try:
        qtbot.waitUntil(lambda: not stream.isRunning(), timeout=4000)
    finally:
        stream.stop()
    assert state["released"] >= 1
