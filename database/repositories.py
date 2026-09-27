"""Репозитории — CRUD-операции для работы с моделями."""

from datetime import datetime, timedelta

from database.db import SessionLocal
from database.models import AppSetting, Event, User
from auth.password_utils import hash_password, verify_password
from core.validators import Validators
from utils.logger import get_logger

logger = get_logger(__name__)


def _detach(session, obj):
    """Снимает объект с сессии, оставляя уже загруженные поля читаемыми."""
    if obj is not None:
        session.expunge(obj)
    return obj


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
            return _detach(session, user)
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
            return _detach(session, user)
        finally:
            session.close()

    # ── Запросы ────────────────────────────────────────────────

    @staticmethod
    def get_by_username(username: str) -> User | None:
        session = SessionLocal()
        try:
            return _detach(session, session.query(User).filter_by(username=username).first())
        finally:
            session.close()

    @staticmethod
    def get_by_id(user_id: int) -> User | None:
        session = SessionLocal()
        try:
            return _detach(session, session.query(User).filter_by(id=user_id).first())
        finally:
            session.close()

    @classmethod
    def change_password(cls, user_id: int, old_password: str, new_password: str) -> None:
        """Меняет пароль. Бросает ValueError, если старый пароль неверен или новый слабый."""
        if not Validators.validate_password(new_password):
            raise ValueError("Пароль минимум 8 символов и должен содержать буквы и цифры")

        session = SessionLocal()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if user is None:
                raise ValueError("Пользователь не найден")
            if not verify_password(old_password, user.password_hash):
                raise ValueError("Текущий пароль неверен")
            user.password_hash = hash_password(new_password)
            session.commit()
            logger.info(f"Пароль изменён: {user.username}")
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


class EventRepository:
    """Журнал событий приложения."""

    @staticmethod
    def add(event_type: str, message: str, username: str | None = None) -> Event:
        session = SessionLocal()
        try:
            if username is None:
                from auth.session import Session

                current = Session.current_user()
                if current is not None:
                    username = current.username

            event = Event(
                event_type=event_type[:32],
                message=message[:512],
                username=username,
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            return _detach(session, event)
        finally:
            session.close()

    @staticmethod
    def list_recent(limit: int = 50) -> list[Event]:
        session = SessionLocal()
        try:
            rows = (
                session.query(Event)
                .order_by(Event.created_at.desc(), Event.id.desc())
                .limit(limit)
                .all()
            )
            for row in rows:
                session.expunge(row)
            return rows
        finally:
            session.close()


class SettingsRepository:
    """Источник и порог между запусками. Пустая таблица — значения из config."""

    @staticmethod
    def get(key: str, default: str | None = None) -> str | None:
        session = SessionLocal()
        try:
            row = session.query(AppSetting).filter_by(key=key).first()
            if row is None:
                return default
            return row.value
        finally:
            session.close()

    @staticmethod
    def set(key: str, value: str) -> None:
        session = SessionLocal()
        try:
            row = session.query(AppSetting).filter_by(key=key).first()
            if row is None:
                row = AppSetting(key=key, value=value[:512])
                session.add(row)
            else:
                row.value = value[:512]
            session.commit()
        finally:
            session.close()

    @classmethod
    def camera_source(cls) -> int | str:
        from config import CAMERA

        raw = cls.get("camera_source")
        if raw is None or not raw.strip():
            return CAMERA.source
        return Validators.parse_camera_source(raw)

    @classmethod
    def confidence(cls) -> float:
        from config import DETECTOR

        raw = cls.get("confidence")
        if raw is None or not raw.strip():
            return float(DETECTOR.confidence)
        try:
            return float(raw)
        except ValueError:
            return float(DETECTOR.confidence)

    @classmethod
    def retention_days(cls) -> int:
        raw = cls.get("retention_days")
        if raw is None or not raw.strip():
            return 0
        try:
            return max(0, min(365, int(raw)))
        except ValueError:
            return 0

    @classmethod
    def retention_gb(cls) -> int:
        raw = cls.get("retention_gb")
        if raw is None or not raw.strip():
            return 0
        try:
            return max(0, min(2000, int(raw)))
        except ValueError:
            return 0

    @classmethod
    def grid_source(cls, index: int) -> str:
        raw = cls.get(f"grid_source_{index}")
        if raw is None:
            if index == 0:
                return str(cls.camera_source())
            return ""
        return raw.strip()

    @classmethod
    def grid_selected(cls) -> int:
        raw = cls.get("grid_selected")
        try:
            index = int(raw) if raw is not None else 0
        except ValueError:
            return 0
        return index if 0 <= index <= 3 else 0

    @classmethod
    def zone(cls, index: int):
        from core.zone import parse_zone

        return parse_zone(cls.get(f"zone_{index}"))