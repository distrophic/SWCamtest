"""Тесты валидаторов. Запуск: python -m tests.test_validators"""

from core.validators import Validators


def run_tests():
    tests = [
        # username
        (Validators.validate_username, ("admin",), True),
        (Validators.validate_username, ("ab",), False),
        (Validators.validate_username, ("user name",), False),
        (Validators.validate_username, ("админ",), False),
        (Validators.validate_username, ("user_01",), True),

        # password
        (Validators.validate_password, ("qwerty12",), True),
        (Validators.validate_password, ("12345678",), False),
        (Validators.validate_password, ("password",), False),
        (Validators.validate_password, ("qwe1",), False),
        (Validators.validate_password, ("MyPass2024",), True),

        # email
        (Validators.validate_email, ("user@mail.com",), True),
        (Validators.validate_email, ("user@",), False),
        (Validators.validate_email, ("просто текст",), False),
        (Validators.validate_email, ("a.b@c.co.uk",), True),

        # ip
        (Validators.validate_ip, ("192.168.1.1",), True),
        (Validators.validate_ip, ("999.0.0.1",), False),
        (Validators.validate_ip, ("192.168.1",), False),
        (Validators.validate_ip, ("hello",), False),

        # port
        (Validators.validate_port, (80,), True),
        (Validators.validate_port, (554,), True),
        (Validators.validate_port, (0,), False),
        (Validators.validate_port, (70000,), False),
        (Validators.validate_port, ("8080",), True),

        # camera_source
        (Validators.validate_camera_source, (0,), True),
        (Validators.validate_camera_source, ("rtsp://192.168.1.10:554/stream",), True),
        (Validators.validate_camera_source, ("/tmp/video.mp4",), True),
        (Validators.validate_camera_source, ("просто текст",), False),
        (Validators.validate_camera_source, (-1,), False),

        # resolution
        (Validators.validate_resolution, (1280, 720), True),
        (Validators.validate_resolution, (1920, 1080), True),
        (Validators.validate_resolution, (0, 0), False),
        (Validators.validate_resolution, (10000, 10000), False),

        # fps
        (Validators.validate_fps, (30,), True),
        (Validators.validate_fps, (60,), True),
        (Validators.validate_fps, (0,), False),
        (Validators.validate_fps, (200,), False),
    ]

    print("=" * 60)
    print("🧪 ТЕСТЫ ВАЛИДАТОРОВ")
    print("=" * 60)

    passed = failed = 0
    for method, args, expected in tests:
        result = method(*args)
        ok = result == expected
        status = "✅" if ok else "❌"
        passed += ok
        failed += not ok

        args_str = ", ".join(repr(a) for a in args)
        print(f"{status} {method.__name__}({args_str}) → {result}")

    print("=" * 60)
    print(f"📊 {passed} пройдено, {failed} провалено")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    exit(0 if run_tests() else 1)