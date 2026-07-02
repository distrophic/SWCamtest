"""Запуск GUI-приложения."""

import sys

from PyQt6.QtWidgets import QApplication

from gui.windows.login_window import LoginWindow
from gui.windows.main_window import MainWindow
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
        self.login_window = LoginWindow()
        self.login_window.logged_in.connect(self._show_main)
        self.login_window.show()

    def _show_main(self) -> None:
        self.main_window = MainWindow()
        self.main_window.destroyed.connect(self._show_login)  # logout → снова логин
        self.main_window.show()