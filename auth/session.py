"""Текущая пользовательская сессия."""

from typing import Optional

from database.models import User
from utils.logger import get_logger

logger = get_logger(__name__)


class Session:
    """Глобальная сессия. Хранит текущего залогиненного пользователя."""

    _current_user: Optional[User] = None

    @classmethod
    def login(cls, user: User) -> None:
        cls._current_user = user
        logger.info(f"Сессия открыта: {user.username} (role={user.role})")

    @classmethod
    def logout(cls) -> None:
        if cls._current_user:
            logger.info(f"Сессия закрыта: {cls._current_user.username}")
        cls._current_user = None

    @classmethod
    def current_user(cls) -> Optional[User]:
        return cls._current_user

    @classmethod
    def is_authenticated(cls) -> bool:
        return cls._current_user is not None

    @classmethod
    def has_role(cls, *roles: str) -> bool:
        return cls._current_user is not None and cls._current_user.role in roles