"""Хеширование и проверка паролей."""

from passlib.context import CryptContext

from utils.logger import get_logger

logger = get_logger(__name__)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Хеширует пароль bcrypt'ом."""
    return _pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Проверяет пароль против хеша. Возвращает False при любой ошибке."""
    try:
        return _pwd_context.verify(plain_password, password_hash)
    except Exception as e:
        logger.warning(f"Ошибка проверки пароля: {e}")
        return False