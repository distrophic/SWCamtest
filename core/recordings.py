"""Список файлов записей на диске. В базу кадры не кладутся."""

import time
from pathlib import Path

VIDEO_SUFFIXES = {".mp4", ".avi", ".mkv", ".mov"}


def list_recording_files(root: str | Path, limit: int = 50) -> list[Path]:
    files = _all_recordings(root)
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files[:limit]


def delete_expired_recordings(root: str | Path, days: int) -> int:
    """Удаляет ролики старше days суток. 0 и меньше — ничего не трогает."""
    return rotate_recordings(root, days=days, max_bytes=0)


def rotate_recordings(root: str | Path, days: int = 0, max_bytes: int = 0) -> int:
    """Сначала ролики старше days суток, затем самые старые, пока папка больше max_bytes.

    days <= 0 отключает срок. max_bytes <= 0 отключает объём.
    Последний оставшийся файл не удаляется из-за объёма: это текущий ролик.
    """
    folder = Path(root)
    if not folder.exists():
        return 0
    removed = 0
    if days > 0:
        cutoff = time.time() - days * 86400
        for path in _all_recordings(folder):
            try:
                if path.stat().st_mtime >= cutoff:
                    continue
                path.unlink()
                removed += 1
            except OSError:
                continue
    if max_bytes > 0:
        files = _all_recordings(folder)
        files.sort(key=lambda path: path.stat().st_mtime)
        sizes = []
        total = 0
        for path in files:
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            sizes.append(size)
            total += size
        index = 0
        while total > max_bytes and index < len(files) - 1:
            try:
                files[index].unlink()
                total -= sizes[index]
                removed += 1
            except OSError:
                pass
            index += 1
    _remove_empty_dirs(folder)
    return removed


def _all_recordings(root: str | Path) -> list[Path]:
    folder = Path(root)
    if not folder.exists():
        return []
    return [
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
    ]


def _remove_empty_dirs(folder: Path) -> None:
    for path in sorted(folder.rglob("*"), reverse=True):
        if path == folder or not path.is_dir():
            continue
        try:
            path.rmdir()
        except OSError:
            continue
