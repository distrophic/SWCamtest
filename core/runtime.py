"""Настройки процесса до импорта OpenCV и PyTorch.

На Windows оба пакета приносят свой OpenMP. Без KMP_DUPLICATE_LIB_OK
процесс молча завершается на первом инференсе, уже после строки «YOLO загружен».
YOLO_OFFLINE отключает фоновый запрос статистики ultralytics: он стартует
в отдельном потоке во время первого predict и на Windows совпадает с падением.
"""

import os


def configure_process() -> None:
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    os.environ.setdefault("YOLO_OFFLINE", "True")


def preload_inference() -> None:
    """Импортирует torch и ultralytics до открытия камеры.

    Первый импорт этих библиотек, пока другой поток уже сидит в
    VideoCapture.read(), на Windows портит кучу (0xC0000374) на следующем
    predict. Повторный вызов ничего не делает: модуль уже в sys.modules.
    """
    configure_process()
    from ultralytics import YOLO  # noqa: F401
