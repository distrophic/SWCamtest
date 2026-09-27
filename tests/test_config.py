"""Импорт настроек не должен падать, поля реконнекта обязательны."""

from config import CAMERA, DETECTOR, DATABASE, CameraDefaults


def test_config_imports():
    assert CAMERA.max_reconnect_attempts >= 1
    assert CAMERA.reconnect_delay >= 0
    assert DETECTOR.model_path.endswith("yolov8n.pt")
    assert DETECTOR.min_interval > 0
    assert DATABASE.path.endswith("securewatch.db")


def test_camera_defaults_are_independent():
    left = CameraDefaults(source="synthetic", max_reconnect_attempts=1)
    right = CameraDefaults()
    assert left.source == "synthetic"
    assert left.max_reconnect_attempts == 1
    assert right.max_reconnect_attempts >= 1
