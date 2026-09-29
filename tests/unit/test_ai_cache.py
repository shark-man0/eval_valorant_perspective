from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

import pytest

from valorant_ai_coach.ai import FileResultCache


def test_cache_rejects_unsafe_key(tmp_path: Path) -> None:
    cache = FileResultCache(tmp_path / "cache")
    with pytest.raises(ValueError, match="cache key"):
        cache.get_ai_cache("../outside")


def test_corrupt_cache_entry_is_ignored(tmp_path: Path) -> None:
    cache = FileResultCache(tmp_path / "cache")
    key = "a" * 64
    path = tmp_path / "cache" / "aa" / f"{key}.json"
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")

    assert cache.get_ai_cache(key) is None


def test_cache_read_survives_entry_deleted_before_lru_touch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = FileResultCache(tmp_path / "cache")
    key = "c" * 64
    cache.put_ai_cache(key, {"value": "valid"})
    path = tmp_path / "cache" / "cc" / f"{key}.json"
    original_utime = os.utime
    cache_module = importlib.import_module("valorant_ai_coach.ai.cache")

    def delete_before_touch(
        target: os.PathLike[str] | str, *args: Any, **kwargs: Any
    ) -> None:
        if Path(target) == path:
            path.unlink()
            raise FileNotFoundError(path)
        original_utime(target, *args, **kwargs)

    monkeypatch.setattr(cache_module.os, "utime", delete_before_touch)

    assert cache.get_ai_cache(key) == {"value": "valid"}
    assert not path.exists()


def test_oversized_result_is_not_cached(tmp_path: Path) -> None:
    cache = FileResultCache(tmp_path / "cache", max_entry_bytes=1024)
    key = "b" * 64

    cache.put_ai_cache(key, {"payload": "x" * 2048})

    assert cache.get_ai_cache(key) is None


def test_cache_prunes_oldest_entries_to_count_and_byte_limits(tmp_path: Path) -> None:
    cache = FileResultCache(
        tmp_path / "cache",
        max_entry_bytes=2048,
        max_total_bytes=2048,
        max_entries=2,
    )
    keys = [letter * 64 for letter in ("a", "b", "c")]

    cache.put_ai_cache(keys[0], {"payload": "x" * 700})
    oldest_path = tmp_path / "cache" / "aa" / f"{keys[0]}.json"
    os.utime(oldest_path, ns=(1, 1))
    cache.put_ai_cache(keys[1], {"payload": "y" * 700})
    cache.put_ai_cache(keys[2], {"payload": "z" * 700})

    remaining = list((tmp_path / "cache").rglob("*.json"))
    assert len(remaining) <= 2
    assert sum(path.stat().st_size for path in remaining) <= 2048
    assert cache.get_ai_cache(keys[0]) is None
    assert cache.get_ai_cache(keys[1]) is not None
    assert cache.get_ai_cache(keys[2]) is not None


def test_cache_prune_ignores_entry_deleted_by_another_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = FileResultCache(tmp_path / "cache", max_total_bytes=4096, max_entries=1)
    old_key, new_key = "a" * 64, "b" * 64
    cache.put_ai_cache(old_key, {"value": "old"})
    old_path = tmp_path / "cache" / "aa" / f"{old_key}.json"
    os.utime(old_path, ns=(1, 1))
    original_unlink = Path.unlink

    def unlink_with_competing_delete(path: Path, *args: object, **kwargs: object) -> None:
        if path == old_path:
            original_unlink(path)
            raise FileNotFoundError(path)
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink_with_competing_delete)

    cache.put_ai_cache(new_key, {"value": "new"})

    assert cache.get_ai_cache(new_key) == {"value": "new"}
    assert not old_path.exists()
