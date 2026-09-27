"""Короткий ролик без людей и без камеры: assets/demo/demo.mp4."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.simulator import DEMO_CLIP, _write_demo_clip


def main() -> None:
    DEMO_CLIP.parent.mkdir(parents=True, exist_ok=True)
    _write_demo_clip(DEMO_CLIP)
    print(DEMO_CLIP)


if __name__ == "__main__":
    main()
