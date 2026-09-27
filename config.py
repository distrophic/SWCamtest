"""
Глобальные настройки приложения.
"""
import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _env_str(name: str) -> str:
    return os.getenv(name, "").strip()


def _env_float(name: str, default: float) -> float:
    raw = _env_str(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_source(default: int | str = 0) -> int | str:
    """Индекс камеры, URL или путь. Пустая переменная — значение по умолчанию."""
    raw = _env_str("SECUREWATCH_CAMERA_SOURCE")
    if not raw:
        return default
    if raw.isdigit():
        return int(raw)
    return raw


# --- Пути ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
MODELS_DIR = os.path.join(ASSETS_DIR, "models")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")
DEMO_DIR = os.path.join(ASSETS_DIR, "demo")
DATA_DIR = os.path.join(BASE_DIR, "data")
RECORDINGS_DIR = os.path.join(DATA_DIR, "recordings")
SNAPSHOTS_DIR = os.path.join(DATA_DIR, "snapshots")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

for _d in (DATA_DIR, RECORDINGS_DIR, SNAPSHOTS_DIR, LOGS_DIR, MODELS_DIR, ICONS_DIR, DEMO_DIR):
    os.makedirs(_d, exist_ok=True)


@dataclass
class CameraDefaults:
    source: int | str = 0
    width: int = 1280
    height: int = 720
    fps: int = 30
    max_reconnect_attempts: int = 5
    reconnect_delay: float = 2.0


@dataclass
class DetectorDefaults:
    model_path: str = os.path.join(MODELS_DIR, "yolov8n.pt")
    confidence: float = 0.5
    classes: list[int] = field(default_factory=lambda: list(_watch_classes()))
    min_interval: float = 0.2


@dataclass
class DatabaseDefaults:
    path: str = os.path.join(DATA_DIR, "securewatch.db")
    echo: bool = False


def _watch_classes() -> tuple[int, ...]:
    from core.detections import WATCH_CLASSES

    return WATCH_CLASSES


CAMERA = CameraDefaults(source=_env_source(0))
DETECTOR = DetectorDefaults(
    confidence=_env_float("SECUREWATCH_CONFIDENCE", 0.5),
    min_interval=_env_float("SECUREWATCH_INFERENCE_INTERVAL", 0.2),
)
DATABASE = DatabaseDefaults()
