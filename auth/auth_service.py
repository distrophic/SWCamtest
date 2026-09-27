"""Сервис авторизации — фасад между GUI и БД."""

from typing import Optional

from auth.password_utils import verify_password
from auth.session import Session
from database import UserRepository
from database.models import User
from utils.logger import get_logger

logger = get_logger(__name__)


class AuthService:
    """Тонкая обёртка над UserRepository + Session."""

    @staticmethod
    def login(username: str, password: str) -> Optional[User]:
        """Вход. Возвращает User при успехе или None."""
        user = UserRepository.authenticate(username, password)
        if user:
            Session.login(user)
        return user

    @staticmethod
    def logout() -> None:
        Session.logout()

    @staticmethod
    def register(username: str, password: str, role: str = "viewer") -> User:
        """Регистрация (бросает ValueError при ошибке)."""
        return UserRepository.create(username, password, role)

    @staticmethod
    def must_change_password(user: User) -> bool:
        """True, если у пользователя всё ещё пароль первого запуска."""
        from auth.bootstrap import DEFAULT_ADMIN_PASSWORD

        return verify_password(DEFAULT_ADMIN_PASSWORD, user.password_hash)

    @staticmethod
    def is_default_password(password: str) -> bool:
        from auth.bootstrap import DEFAULT_ADMIN_PASSWORD

        return password == DEFAULT_ADMIN_PASSWORD

    @staticmethod
    def change_password(user_id: int, old_password: str, new_password: str) -> None:
        """Меняет пароль и обновляет хеш в текущей сессии."""
        if AuthService.is_default_password(new_password):
            raise ValueError("Нельзя оставлять пароль по умолчанию")

        UserRepository.change_password(user_id, old_password, new_password)

        current = Session.current_user()
        fresh = UserRepository.get_by_id(user_id)
        if current is not None and fresh is not None and current.id == fresh.id:
            current.password_hash = fresh.password_hash

        try:
            from database.repositories import EventRepository

            EventRepository.add("auth", "Пароль изменён")
        except Exception:
            logger.exception("Не удалось записать событие смены пароля")