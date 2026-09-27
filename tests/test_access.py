"""Роли в главном окне. Источник synthetic, детектор может не загрузиться."""

from auth import Session
from database.repositories import SettingsRepository, UserRepository
from gui.windows.main_window import MainWindow


def _window(qtbot, username: str, password: str, role: str) -> MainWindow:
    SettingsRepository.set("camera_source", "synthetic")
    user = UserRepository.create(username, password, role)
    Session.login(user)
    window = MainWindow()
    qtbot.addWidget(window)
    return window


def test_viewer_controls_stay_disabled(qtbot, users_db):
    window = _window(qtbot, "guest", "guest1234", "viewer")
    try:
        qtbot.waitUntil(lambda: window._camera_up, timeout=4000)
        assert window.rec_btn.isEnabled() is False
        assert window.auto_checkbox.isEnabled() is False
        assert window.connect_btn.isEnabled() is False
        assert window.zone_btn.isEnabled() is False
        assert len(window.tiles) == 4
        assert window.pause_btn.isHidden() is True
        assert window.snapshot_btn.isEnabled() is False
        assert window.users_btn.isHidden() is True
    finally:
        window.close()


def test_operator_can_record_when_source_is_up(qtbot, users_db):
    window = _window(qtbot, "oper", "operator1", "operator")
    try:
        qtbot.waitUntil(lambda: window.rec_btn.isEnabled(), timeout=4000)
        assert window.connect_btn.isEnabled() is True
        assert window.users_btn.isHidden() is True
    finally:
        window.close()


def test_starts_with_one_camera_and_button_opens_grid(qtbot, users_db):
    window = _window(qtbot, "griduser", "gridpass1", "operator")
    window.show()
    try:
        assert window._grid_mode is False
        assert window.view_mode_btn.text() == "Сетка"
        assert window.tiles[window._selected].isVisible() is True
        assert window.tiles[1].isVisible() is False
        window.view_mode_btn.click()
        assert window._grid_mode is True
        assert window.view_mode_btn.text() == "Одна камера"
        assert window.tiles[1].isVisible() is True
        window.view_mode_btn.click()
        assert window.tiles[1].isVisible() is False
    finally:
        window.close()


def test_admin_sees_user_button(qtbot, users_db):
    window = _window(qtbot, "boss", "adminpass1", "admin")
    try:
        assert window.users_btn.isHidden() is False
        assert window.connect_btn.isEnabled() is True
        assert window.zone_btn.isEnabled() is True
        assert window.retention_spin.lineEdit().isReadOnly() is True
        assert window.retention_gb_spin.lineEdit().isReadOnly() is True
    finally:
        window.close()
