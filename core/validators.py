"""Валидаторы пользовательского ввода."""

import re
from pathlib import Path


class Validators:
    """Статические методы проверки данных. Возвращают bool."""

    # ── Пользователи ──────────────────────────

    @staticmethod
    def validate_username(username: str) -> bool:
        if not isinstance(username, str):
            return False
        return bool(re.match(r'^[a-zA-Z0-9_]{3,32}$', username))

    @staticmethod
    def validate_password(password: str) -> bool:
        if not isinstance(password, str) or len(password) < 8:
            return False
        has_letter = bool(re.search(r'[a-zA-Z]', password))
        has_digit = bool(re.search(r'\d', password))
        return has_letter and has_digit

    @staticmethod
    def validate_email(email: str) -> bool:
        if not isinstance(email, str):
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    # ── Сеть ──────────────────────────────────

    @staticmethod
    def validate_ip(ip: str) -> bool:
        if not isinstance(ip, str):
            return False
        if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
            return False
        return all(0 <= int(octet) <= 255 for octet in ip.split('.'))

    @staticmethod
    def validate_port(port: int | str) -> bool:
        try:
            return 1 <= int(port) <= 65535
        except (ValueError, TypeError):
            return False

    # ── Камеры ────────────────────────────────

    @staticmethod
    def validate_camera_source(source: int | str) -> bool:
        if isinstance(source, int):
            return source >= 0

        if not isinstance(source, str) or not source.strip():
            return False

        if source.isdigit():
            return True

        if source.startswith(('rtsp://', 'http://', 'https://')):
            return len(source) > 10

        try:
            return Path(source).suffix.lower() in {'.mp4', '.avi', '.mkv', '.mov'}
        except (ValueError, OSError):
            return False

    @staticmethod
    def validate_resolution(width: int, height: int) -> bool:
        try:
            w, h = int(width), int(height)
            return 160 <= w <= 7680 and 120 <= h <= 4320
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_fps(fps: int | float) -> bool:
        try:
            return 1 <= float(fps) <= 120
        except (ValueError, TypeError):
            return False