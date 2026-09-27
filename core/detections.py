"""Человек и сущность. Сущность — транспорт и животные COCO, не человек."""

from __future__ import annotations

PERSON_CLASS = 0
# bicycle, car, motorcycle, bus, truck, bird, cat, dog, horse, sheep, cow
ENTITY_CLASSES = (1, 2, 3, 5, 7, 14, 15, 16, 17, 18, 19)
WATCH_CLASSES = (PERSON_CLASS, *ENTITY_CLASSES)


def detection_kind(class_id: int) -> str:
    return "person" if int(class_id) == PERSON_CLASS else "entity"


def box_kind(box: tuple) -> str:
    if len(box) >= 6 and box[5] == "entity":
        return "entity"
    return "person"


def persons_only(boxes: list) -> list:
    return [box for box in boxes if box_kind(box) == "person"]


def entities_only(boxes: list) -> list:
    return [box for box in boxes if box_kind(box) == "entity"]
