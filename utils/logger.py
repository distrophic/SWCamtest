"""
Централизованный логгер для всего проекта.
Цветной вывод в консоль + ротация файлов.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

import colorlog

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Возвращает настроенный логгер.

    :param name:  имя логгера (обычно __name__)
    :param level: уровень логирования
    """
    logger = logging.getLogger(name)
    if logger.handlers:                # уже настроен — отдаём как есть
        return logger

    logger.setLevel(level)

    # === Консоль (цветной) ===
    console = colorlog.StreamHandler()
    console.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        log_colors={
            "DEBUG":    "cyan",
            "INFO":     "green",
            "WARNING":  "yellow",
            "ERROR":    "red",
            "CRITICAL": "bold_red",
        },
    ))
    logger.addHandler(console)

    # === Файл (с ротацией) ===
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "securewatch.log"),
        maxBytes=5 * 1024 * 1024,      # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(file_handler)

    return logger