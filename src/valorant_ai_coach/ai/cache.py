from __future__ import annotations

import json
import os
import re
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any


class FileResultCache:
    """Small atomic cache for validated AI JSON; image bytes and API keys are never stored."""

    _key_pattern = re.compile(r"^[a-f0-9]{64}$")
    _default_max_total_bytes = 256 * 1024 * 1024
    _default_max_entries = 512

    def __init__(
        self,
        root: Path,
        *,
        max_entry_bytes: int = 5 * 1024 * 1024,
        max_total_bytes: int = _default_max_total_bytes,
        max_entries: int = _default_max_entries,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.max_entry_bytes = max(1024, int(max_entry_bytes))
        self.max_total_bytes = max(1024, int(max_total_bytes))
        self.max_entries = max(1, int(max_entries))

    def _path(self, key: str) -> Path:
        if not self._key_pattern.fullmatch(key):
            raise ValueError("AI cache keyが不正です")
        return self.root / key[:2] / f"{key}.json"

    def get_ai_cache(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        try:
            if not path.is_file() or path.stat().st_size > self.max_entry_bytes:
                return None
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict):
            return None
        with suppress(OSError):
            os.utime(path, None)
        return value

    def put_ai_cache(self, key: str, value: dict[str, Any]) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > self.max_entry_bytes:
            return
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(encoded)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        self._prune()

    def _prune(self) -> None:
        """Best-effort mtime LRU eviction after a write."""

        entries: list[tuple[int, int, Path]] = []
        try:
            paths = self.root.glob("[0-9a-f][0-9a-f]/*.json")
            for path in paths:
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if not path.is_file():
                    continue
                entries.append((stat.st_mtime_ns, stat.st_size, path))
        except OSError:
            return

        total_bytes = sum(size for _mtime, size, _path in entries)
        entry_count = len(entries)
        for _mtime, size, path in sorted(entries, key=lambda item: (item[0], str(item[2]))):
            if total_bytes <= self.max_total_bytes and entry_count <= self.max_entries:
                break
            try:
                path.unlink()
            except FileNotFoundError:
                # A concurrent cleanup already removed this stale entry.
                total_bytes -= size
                entry_count -= 1
            except OSError:
                # A concurrent or filesystem error should not stop best-effort pruning.
                continue
            else:
                total_bytes -= size
                entry_count -= 1


__all__ = ["FileResultCache"]
