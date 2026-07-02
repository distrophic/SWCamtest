"""Точка входа SecureWatch."""

import sys

from auth import ensure_first_admin
from database import init_db
from gui.app import SecureWatchApp
from utils.logger import get_logger

logger = get_logger(__name__)


def bootstrap() -> None:
    """Инициализация перед запуском GUI."""
    logger.info("=" * 60)
    logger.info("🚀 Запуск SecureWatch")
    logger.info("=" * 60)

    init_db()
    ensure_first_admin()


def main() -> int:
    bootstrap()
    app = SecureWatchApp(sys.argv)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())