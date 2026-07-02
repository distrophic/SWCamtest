"""Репозитории — CRUD-операции для работы с моделями."""

from datetime import datetime, timedelta

from database.db import SessionLocal
from database.models import User
from auth.password_utils import hash_password, verify_password
from core.validators import Validators
from utils.logger import get_logger

logger = get_logger(__name__)


class UserRepository:
    """Операции с пользователями."""

    LOCK_AFTER_ATTEMPTS = 5
    LOCK_DURATION_MINUTES = 15
    ALLOWED_ROLES = ("admin", "operator", "viewer")

    # ── Создание ───────────────────────────────────────────────

    @classmethod
    def create(cls, username: str, password: str, role: str = "viewer") -> User:
        """Создаёт пользователя. Бросает ValueError при ошибке."""

        if not Validators.validate_username(username):
            raise ValueError("Некорректное имя пользователя (3-32 символа, латиница/цифры/_)")

        if not Validators.validate_password(password):
            raise ValueError("Пароль минимум 8 символов и должен содержать буквы и цифры")

        if role not in cls.ALLOWED_ROLES:
            raise ValueError(f"Неизвестная роль: {role}")

        session = SessionLocal()
        try:
            if session.query(User).filter_by(username=username).first():
                raise ValueError("Пользователь с таким именем уже существует")

            user = User(
                username=username,
                password_hash=hash_password(password),
                role=role,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            logger.info(f"Создан пользователь: {username} (role={role})")
            return user
        finally:
            session.close()

    # ── Авторизация ────────────────────────────────────────────

    @classmethod
    def authenticate(cls, username: str, password: str) -> User | None:
        """Проверяет логин/пароль. Возвращает User или None."""

        session = SessionLocal()
        try:
            user = session.query(User).filter_by(username=username).first()

            if not user:
                logger.warning(f"Попытка входа с несуществующим логином: {username}")
                return None

            if not user.is_active:
                logger.warning(f"Попытка входа в отключённый аккаунт: {username}")
                return None

            if user.locked_until and user.locked_until > datetime.utcnow():
                logger.warning(f"Аккаунт заблокирован до {user.locked_until}: {username}")
                return None

            if not verify_password(password, user.password_hash):
                user.failed_login_attempts += 1

                if user.failed_login_attempts >= cls.LOCK_AFTER_ATTEMPTS:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=cls.LOCK_DURATION_MINUTES)
                    logger.warning(f"Аккаунт заблокирован на {cls.LOCK_DURATION_MINUTES} мин: {username}")

                session.commit()
                return None

            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login_at = datetime.utcnow()
            session.commit()
            session.refresh(user)

            logger.info(f"Успешный вход: {username}")
            return user
        finally:
            session.close()

    # ── Запросы ────────────────────────────────────────────────

    @staticmethod
    def get_by_username(username: str) -> User | None:
        session = SessionLocal()
        try:
            return session.query(User).filter_by(username=username).first()
        finally:
            session.close()

    @staticmethod
    def get_by_id(user_id: int) -> User | None:
        session = SessionLocal()
        try:
            return session.query(User).filter_by(id=user_id).first()
        finally:
            session.close()

    @staticmethod
    def count() -> int:
        session = SessionLocal()
        try:
            return session.query(User).count()
        finally:
            session.close()

    @classmethod
    def is_first_run(cls) -> bool:
        """True, если в БД ещё нет ни одного пользователя."""
        return cls.count() == 0