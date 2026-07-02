"""Подключение к БД и базовый класс моделей."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DATABASE
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Настройки ──────────────────────────────────────────────────

DB_PATH = Path(DATABASE.path)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=DATABASE.echo,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def init_db() -> None:
    """Создаёт все таблицы, если их ещё нет."""
    from database import models  # noqa: F401 — регистрируем модели в Base
    Base.metadata.create_all(engine)
    logger.info(f"База данных инициализирована: {DB_PATH}")