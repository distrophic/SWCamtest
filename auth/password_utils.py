"""Хеширование и проверка паролей."""

import bcrypt

from utils.logger import get_logger

logger = get_logger(__name__)


def hash_password(password: str) -> str:
    """Хеширует пароль bcrypt'ом."""
    data = password.encode("utf-8")
    if len(data) > 72:
        raise ValueError("Пароль слишком длинный для bcrypt (максимум 72 байта)")
    return bcrypt.hashpw(data, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Проверяет пароль против хеша. Возвращает False при любой ошибке."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except Exception as exc:
        logger.warning(f"Ошибка проверки пароля: {exc}")
        return False
