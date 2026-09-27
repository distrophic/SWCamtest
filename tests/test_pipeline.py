"""Пайплайн на synthetic без YOLO и без реальной камеры."""

from core.pipeline import Pipeline


def test_synthetic_pipeline_emits_frame_and_stops(qtbot):
    pipeline = Pipeline()
    frames: list = []
    pipeline.frame_ready.connect(frames.append)
    pipeline.start("synthetic", 0.5, with_detector=False)
    try:
        qtbot.waitUntil(lambda: len(frames) >= 1, timeout=4000)
        assert frames[0].ndim == 3
    finally:
        pipeline.stop()
    assert pipeline.is_running() is False
