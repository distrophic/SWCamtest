"""Тесты валидаторов. Запуск: pytest tests/test_validators.py"""

import pytest

from core.validators import Validators


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("admin", True),
        ("ab", False),
        ("user name", False),
        ("админ", False),
        ("user_01", True),
    ],
)
def test_username(value, expected):
    assert Validators.validate_username(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("qwerty12", True),
        ("12345678", False),
        ("password", False),
        ("qwe1", False),
        ("MyPass2024", True),
    ],
)
def test_password(value, expected):
    assert Validators.validate_password(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("user@mail.com", True),
        ("user@", False),
        ("просто текст", False),
        ("a.b@c.co.uk", True),
    ],
)
def test_email(value, expected):
    assert Validators.validate_email(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("192.168.1.1", True),
        ("999.0.0.1", False),
        ("192.168.1", False),
        ("hello", False),
    ],
)
def test_ip(value, expected):
    assert Validators.validate_ip(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (80, True),
        (554, True),
        (0, False),
        (70000, False),
        ("8080", True),
    ],
)
def test_port(value, expected):
    assert Validators.validate_port(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, True),
        ("rtsp://192.168.1.10:554/stream", True),
        ("http://camera.local/stream", True),
        ("https://example.com/video.mjpeg", True),
        ("synthetic", True),
        ("simulator", True),
        ("/tmp/video.mp4", True),
        ("просто текст", False),
        (-1, False),
    ],
)
def test_camera_source(value, expected):
    assert Validators.validate_camera_source(value) is expected


def test_parse_camera_source():
    assert Validators.parse_camera_source("0") == 0
    assert Validators.parse_camera_source(1) == 1
    assert Validators.parse_camera_source("rtsp://host/stream") == "rtsp://host/stream"
    assert Validators.parse_camera_source(" synthetic ") == "synthetic"


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (1280, 720, True),
        (1920, 1080, True),
        (0, 0, False),
        (10000, 10000, False),
    ],
)
def test_resolution(width, height, expected):
    assert Validators.validate_resolution(width, height) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (30, True),
        (60, True),
        (0, False),
        (200, False),
    ],
)
def test_fps(value, expected):
    assert Validators.validate_fps(value) is expected
