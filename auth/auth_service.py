"""Сервис авторизации — фасад между GUI и БД."""

from typing import Optional

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