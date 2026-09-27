"""Запуск GUI-приложения."""

import sys

from PyQt6.QtWidgets import QApplication, QDialog

from auth import AuthService, Session
from gui.windows.login_window import LoginWindow
from gui.windows.main_window import MainWindow
from gui.windows.password_dialog import PasswordDialog
from utils.logger import get_logger

logger = get_logger(__name__)


class SecureWatchApp:
    """Контроллер окон приложения."""

    def __init__(self, argv: list[str]):
        self.app = QApplication(argv)
        self.app.setApplicationName("SecureWatch")

        self.login_window: LoginWindow | None = None
        self.main_window: MainWindow | None = None

    def run(self) -> int:
        self._show_login()
        return self.app.exec()

    def _show_login(self) -> None:
        window = LoginWindow()
        self.login_window = window
        window.logged_in.connect(self._show_main)
        window.closed.connect(lambda closed=window: self._on_login_closed(closed))
        window.show()

    def _on_login_closed(self, window: LoginWindow) -> None:
        """Крестик на текущем окне входа без сессии завершает процесс."""
        if window is not self.login_window:
            return
        if Session.is_authenticated():
            return
        self.app.quit()

    def _show_main(self) -> None:
        user = Session.current_user()
        if user is not None and AuthService.must_change_password(user):
            dialog = PasswordDialog(user, force=True)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                AuthService.logout()
                self._show_login()
                return

        self.main_window = MainWindow()
        self.main_window.destroyed.connect(self._show_login)
        self.main_window.show()