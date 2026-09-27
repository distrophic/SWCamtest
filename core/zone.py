"""Зона кадра. Координаты нормализованы: 0..1 от ширины и высоты."""

from __future__ import annotations

Zone = tuple[float, float, float, float]
Box = tuple[int, int, int, int, float]


def parse_zone(raw: str | None) -> Zone | None:
    if raw is None or not raw.strip():
        return None
    parts = raw.split(",")
    if len(parts) != 4:
        return None
    try:
        x, y, w, h = (float(part) for part in parts)
    except ValueError:
        return None
    if w <= 0.01 or h <= 0.01:
        return None
    x = min(max(x, 0.0), 1.0)
    y = min(max(y, 0.0), 1.0)
    w = min(w, 1.0 - x)
    h = min(h, 1.0 - y)
    if w <= 0.01 or h <= 0.01:
        return None
    return (x, y, w, h)


def format_zone(zone: Zone | None) -> str:
    if zone is None:
        return ""
    return ",".join(f"{value:.4f}" for value in zone)


def people_in_zone(
    boxes: list[Box],
    zone: Zone | None,
    frame_height: int,
    frame_width: int,
) -> list[Box]:
    """Оставляет людей, чей центр попал в зону. Без зоны возвращает все рамки."""
    if zone is None or frame_height <= 0 or frame_width <= 0:
        return list(boxes)
    left = zone[0] * frame_width
    top = zone[1] * frame_height
    right = (zone[0] + zone[2]) * frame_width
    bottom = (zone[1] + zone[3]) * frame_height
    kept: list[Box] = []
    for box in boxes:
        center_x = (box[0] + box[2]) / 2
        center_y = (box[1] + box[3]) / 2
        if left <= center_x <= right and top <= center_y <= bottom:
            kept.append(box)
    return kept
