"""Фильтр зоны без камеры и без окна."""

from core.zone import people_in_zone


def test_without_zone_every_box_stays():
    boxes = [(0, 0, 10, 10, 0.9)]
    assert people_in_zone(boxes, None, 100, 100) == boxes


def test_center_inside_zone_is_kept():
    boxes = [(10, 10, 30, 30, 0.8), (80, 80, 90, 90, 0.7)]
    zone = (0.0, 0.0, 0.5, 0.5)
    assert people_in_zone(boxes, zone, 100, 100) == [boxes[0]]


def test_unknown_frame_size_does_not_drop_boxes():
    boxes = [(1, 1, 4, 4, 0.5)]
    assert people_in_zone(boxes, (0.2, 0.2, 0.2, 0.2), 0, 0) == boxes
