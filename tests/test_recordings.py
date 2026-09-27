"""Список файлов записей без базы и без камеры."""

import os

from core.recordings import delete_expired_recordings, list_recording_files, rotate_recordings


def test_list_recordings_newest_first(tmp_path):
    day = tmp_path / "2026-09-27"
    day.mkdir()
    older = day / "old.mp4"
    newer = day / "new.mp4"
    note = day / "ignore.txt"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    note.write_bytes(b"no")
    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_700_000_100, 1_700_000_100))

    files = list_recording_files(tmp_path)
    assert [path.name for path in files] == ["new.mp4", "old.mp4"]


def test_delete_expired_keeps_fresh_files(tmp_path):
    day = tmp_path / "2026-09-27"
    day.mkdir()
    old = day / "old.mp4"
    fresh = day / "fresh.mp4"
    old.write_bytes(b"old")
    fresh.write_bytes(b"fresh")
    os.utime(old, (1_700_000_000, 1_700_000_000))
    fresh.touch()

    assert delete_expired_recordings(tmp_path, 0) == 0
    assert old.exists()
    removed = delete_expired_recordings(tmp_path, 1)
    assert removed == 1
    assert old.exists() is False
    assert fresh.exists() is True
    assert day.exists() is True


def test_rotate_drops_oldest_until_under_size(tmp_path):
    day = tmp_path / "2026-09-27"
    day.mkdir()
    oldest = day / "a.mp4"
    middle = day / "b.mp4"
    newest = day / "c.mp4"
    oldest.write_bytes(b"a" * 100)
    middle.write_bytes(b"b" * 100)
    newest.write_bytes(b"c" * 100)
    os.utime(oldest, (1_700_000_000, 1_700_000_000))
    os.utime(middle, (1_700_000_100, 1_700_000_100))
    os.utime(newest, (1_700_000_200, 1_700_000_200))

    removed = rotate_recordings(tmp_path, days=0, max_bytes=150)
    assert removed == 2
    assert oldest.exists() is False
    assert middle.exists() is False
    assert newest.exists() is True
