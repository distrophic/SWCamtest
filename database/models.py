"""ORM-модели базы данных."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from database.db import Base


class User(Base):
    """Пользователь системы."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(32), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False, default="viewer")  # admin / operator / viewer

    is_active = Column(Boolean, nullable=False, default=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role}>"


class AppSetting(Base):
    """Пара источника и порога, выбранные в окне. Не секреты камеры отдельным видом."""

    __tablename__ = "settings"

    key = Column(String(64), primary_key=True)
    value = Column(String(512), nullable=False)

    def __repr__(self) -> str:
        return f"<AppSetting {self.key}={self.value!r}>"


class Event(Base):
    """Журнал событий: запись, камера, детекция. Не хранит кадры."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    event_type = Column(String(32), nullable=False, index=True)
    message = Column(String(512), nullable=False)
    username = Column(String(32), nullable=True)

    def __repr__(self) -> str:
        return f"<Event id={self.id} type={self.event_type!r}>"