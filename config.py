"""
Глобальные настройки приложения.
"""
import os
from dataclasses import dataclass, field

# --- Пути ---
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR      = os.path.join(BASE_DIR, "assets")
MODELS_DIR      = os.path.join(ASSETS_DIR, "models")
ICONS_DIR       = os.path.join(ASSETS_DIR, "icons")
DATA_DIR        = os.path.join(BASE_DIR, "data")
RECORDINGS_DIR  = os.path.join(DATA_DIR, "recordings")
LOGS_DIR        = os.path.join(BASE_DIR, "logs")

# создаём недостающие папки
for _d in (DATA_DIR, RECORDINGS_DIR, LOGS_DIR, MODELS_DIR, ICONS_DIR):
    os.makedirs(_d, exist_ok=True)


# --- Камера по умолчанию ---
@dataclass
class CameraDefaults:
    source: int | str = 0
    width: int        = 1280
    height: int       = 720
    fps: int          = 30

# --- Детекция ---
@dataclass
class DetectorDefaults:
    model_path: str    = os.path.join(MODELS_DIR, "yolov8n.pt")
    confidence: float  = 0.5
    classes: list[int] = field(default_factory=lambda: [0])   # 0 = person в COCO

# --- Детекция ---
@dataclass
@dataclass
class DatabaseDefaults:
    path: str = os.path.join(DATA_DIR, "securewatch.db")
    echo: bool = False

CAMERA   = CameraDefaults()
DETECTOR = DetectorDefaults()
DATABASE = DatabaseDefaults()

