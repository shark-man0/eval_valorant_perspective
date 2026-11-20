"""Content-addressed feature cache: each archive is processed once per extractor version."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np


class FeatureStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def path(self, archive_sha256: str, extractor_id: str) -> Path:
        return self.root / f"{extractor_id}__{archive_sha256[:20]}.npz"

    def get_or_compute(self, archive_sha256: str, extractor_id: str,
                       compute: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        """Arrays are stored as NumPy arrays; ``meta`` (if present) as JSON."""
        target = self.path(archive_sha256, extractor_id)
        if target.exists():
            self.hits += 1
            with np.load(target, allow_pickle=False) as data:
                loaded: dict[str, Any] = {k: data[k] for k in data.files if k != "meta_json"}
                if "meta_json" in data.files:
                    loaded["meta"] = json.loads(str(data["meta_json"]))
            return loaded
        self.misses += 1
        result = compute()
        arrays = {k: np.asarray(v) for k, v in result.items() if k != "meta"}
        if "meta" in result:
            arrays["meta_json"] = np.asarray(json.dumps(result["meta"], ensure_ascii=False))
        tmp = target.with_name(target.stem + ".tmp.npz")
        np.savez_compressed(tmp, **arrays)  # type: ignore[arg-type]
        tmp.replace(target)
        return result
