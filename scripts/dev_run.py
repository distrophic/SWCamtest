"""Локальный запуск без окна входа. Пароль не проверяется.

Только для отладки на своей машине. Обычный запуск по-прежнему python main.py.

    py -3 scripts/dev_run.py
    py -3 scripts/dev_run.py viewer_name
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.runtime import configure_process

configure_process()

from PyQt6.QtWidgets import QApplication

from auth.bootstrap import DEFAULT_ADMIN_USERNAME, ensure_first_admin
from auth.session import Session
from database import UserRepository, init_db
from gui.windows.main_window import MainWindow
from utils.logger import get_logger

logger = get_logger(__name__)


def main() -> int:
    username = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADMIN_USERNAME
    init_db()
    ensure_first_admin()

    user = UserRepository.get_by_username(username)
    if user is None:
        raise SystemExit(f"Пользователь {username!r} не найден. Окно входа не открываю.")

    logger.warning("DEV: вход без пароля, пользователь %s (%s)", username, user.role)
    Session.login(user)

    app = QApplication(sys.argv)
    app.setApplicationName("SecureWatch")
    window = MainWindow()
    window.setWindowTitle("SecureWatch (dev, без входа)")
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
