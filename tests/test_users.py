"""Пользователи и журнал на временной SQLite, без файла приложения."""

import pytest
from sqlalchemy import inspect

from auth import AuthService, Session
from auth.bootstrap import DEFAULT_ADMIN_PASSWORD, ensure_first_admin
from database.repositories import EventRepository, SettingsRepository, UserRepository


def test_user_stays_readable_after_session_close(users_db):
    created = UserRepository.create("admin", "admin12345", "admin")
    assert created.username == "admin"

    logged = UserRepository.authenticate("admin", "admin12345")
    assert logged is not None
    assert inspect(logged).detached
    assert logged.role == "admin"
    assert logged.username == "admin"


def test_password_change_and_default_rejected(users_db):
    user = UserRepository.create("admin", "admin12345", "admin")
    Session.login(user)
    assert AuthService.must_change_password(user)

    with pytest.raises(ValueError):
        AuthService.change_password(user.id, "admin12345", "admin12345")

    AuthService.change_password(user.id, "admin12345", "BetterPass1")
    assert AuthService.must_change_password(Session.current_user()) is False
    assert UserRepository.authenticate("admin", "admin12345") is None
    assert UserRepository.authenticate("admin", "BetterPass1") is not None

    events = EventRepository.list_recent()
    assert any(event.event_type == "auth" for event in events)
    assert events[0].message == "Пароль изменён"


def test_bootstrap_does_not_log_password(users_db, monkeypatch):
    messages: list[str] = []
    monkeypatch.setattr(
        "auth.bootstrap.logger.warning",
        lambda message: messages.append(str(message)),
    )
    assert ensure_first_admin() is True
    text = "\n".join(messages)
    assert DEFAULT_ADMIN_PASSWORD not in text
    assert any("Смените пароль" in message for message in messages)


def test_settings_roundtrip(users_db):
    from config import CAMERA

    assert SettingsRepository.camera_source() == CAMERA.source
    SettingsRepository.set("camera_source", "synthetic")
    SettingsRepository.set("confidence", "0.25")
    assert SettingsRepository.camera_source() == "synthetic"
    assert SettingsRepository.confidence() == 0.25
