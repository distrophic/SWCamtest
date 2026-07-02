
from database import UserRepository
from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin12345"


def ensure_first_admin() -> bool:
    """
    Создаёт дефолтного админа, если в БД ещё нет ни одного пользователя.

    :return: True — админ был создан, False — БД уже содержит юзеров
    """
    if not UserRepository.is_first_run():
        return False

    UserRepository.create(
        username=DEFAULT_ADMIN_USERNAME,
        password=DEFAULT_ADMIN_PASSWORD,
        role="admin",
    )

    logger.warning("=" * 60)
    logger.warning("⚠  СОЗДАН ДЕФОЛТНЫЙ АДМИНИСТРАТОР")
    logger.warning(f"   Логин:  {DEFAULT_ADMIN_USERNAME}")
    logger.warning(f"   Пароль: {DEFAULT_ADMIN_PASSWORD}")
    logger.warning("⚠  СМЕНИТЕ ПАРОЛЬ ПОСЛЕ ПЕРВОГО ВХОДА!")
    logger.warning("=" * 60)

    return True