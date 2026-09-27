"""Ограничение частоты детекции без загрузки YOLO."""

import numpy as np

from core.detector import PersonDetector


class _EmptyResult:
    boxes = None


class _FakeModel:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, frame, conf, classes, verbose=False):
        self.calls += 1
        return [_EmptyResult()]


def test_submit_without_model_is_ignored(qtbot):
    detector = PersonDetector(model_path="missing.pt", min_interval=0)
    received: list = []
    detector.detections_ready.connect(received.append)
    detector.submit(np.zeros((8, 8, 3), dtype=np.uint8))
    qtbot.wait(50)
    assert received == []
    assert detector._busy is False


def test_submit_respects_min_interval(qtbot):
    detector = PersonDetector(min_interval=60)
    model = _FakeModel()
    detector.model = model
    frame = np.zeros((8, 8, 3), dtype=np.uint8)

    detector.submit(frame)
    qtbot.waitUntil(lambda: model.calls == 1 and detector._busy is False, timeout=2000)

    detector.submit(frame)
    qtbot.wait(100)
    assert model.calls == 1
