"""Виджет видео на синтетическом кадре, без камеры."""

import numpy as np

from gui.widgets.video_widget import VideoWidget


def test_update_frame_sets_pixmap(qtbot):
    widget = VideoWidget()
    qtbot.addWidget(widget)
    widget.show()
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    frame[:, :, 1] = 128
    widget.set_detections([(4, 20, 30, 40, 0.91)])
    widget.update_frame(frame)
    qtbot.waitUntil(lambda: widget.last_frame() is not None, timeout=1000)

    assert widget.grab().isNull() is False
    last = widget.last_frame()
    assert last is not None
    assert last.shape == frame.shape
    assert int(last[0, 0, 1]) == 128
