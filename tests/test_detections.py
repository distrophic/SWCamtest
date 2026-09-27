"""Разделение человека и сущности без модели."""

from core.detections import box_kind, detection_kind, entities_only, persons_only


def test_person_class_is_person():
    assert detection_kind(0) == "person"
    assert detection_kind(2) == "entity"


def test_old_box_without_kind_counts_as_person():
    box = (0, 0, 10, 10, 0.9)
    assert box_kind(box) == "person"
    assert persons_only([box]) == [box]
    assert entities_only([box]) == []


def test_entity_box_is_not_a_person():
    person = (0, 0, 10, 10, 0.9, "person")
    entity = (20, 20, 40, 40, 0.8, "entity")
    assert persons_only([person, entity]) == [person]
    assert entities_only([person, entity]) == [entity]
