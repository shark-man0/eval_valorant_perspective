"""Incremental registry of private recording archives for continual learning.

Adding a recording never re-splits earlier ones: each physical match is
assigned once, deterministically, and every derived sample inherits that
assignment. The registry stores hashes and split decisions only; the archives
themselves stay private.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SPLITS = ("TRAIN", "VALIDATION", "FROZEN_TEST")
DEFAULT_RATIOS = {"TRAIN": 0.6, "VALIDATION": 0.2, "FROZEN_TEST": 0.2}


def file_sha256(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def _bucket(physical_match_id: str, seed: str) -> float:
    value = hashlib.sha256(f"{seed}:{physical_match_id}".encode("utf-8")).digest()  # noqa: UP012
    return int.from_bytes(value[:8], "big") / 2**64


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    physical_match_id: str
    archive: str
    archive_sha256: str
    archive_bytes: int
    split: str
    added_at: str
    order: int
    note: str = ""


class LeakageError(ValueError):
    """A physical match would appear in more than one split."""


class DatasetRegistry:
    """JSON-backed, append-only registry. ``path`` lives in a private directory."""

    def __init__(self, path: Path, *, seed: str = "continual-v1",
                 ratios: dict[str, float] | None = None) -> None:
        self.path = path
        self.seed = seed
        self.ratios = dict(ratios or DEFAULT_RATIOS)
        if set(self.ratios) != set(SPLITS) or abs(sum(self.ratios.values()) - 1) > 1e-9:
            raise ValueError("Ratios must cover TRAIN/VALIDATION/FROZEN_TEST and sum to 1")
        self.records: dict[str, SourceRecord] = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("seed") != seed:
                raise ValueError("Registry seed differs; splits would change")
            self.ratios = data["ratios"]
            for item in data["sources"]:
                record = SourceRecord(**item)
                self.records[record.source_id] = record
        self.validate()

    # Split assignment ------------------------------------------------------
    def split_for(self, physical_match_id: str) -> str:
        for record in self.records.values():
            if record.physical_match_id == physical_match_id:
                return record.split
        bucket = _bucket(physical_match_id, self.seed)
        edge = 0.0
        for split in SPLITS:
            edge += self.ratios[split]
            if bucket < edge:
                return split
        return SPLITS[-1]

    def intake(self, source_id: str, physical_match_id: str, archive: Path, *,
               split: str | None = None, note: str = "") -> tuple[SourceRecord, bool]:
        """Register an archive. Returns (record, added). Re-intake is a no-op."""
        digest = file_sha256(archive)
        for record in self.records.values():
            if record.archive_sha256 == digest:
                if record.source_id != source_id:
                    raise ValueError(f"Duplicate content: {source_id} == {record.source_id}")
                return record, False
        if source_id in self.records:
            raise ValueError(f"{source_id} already registered with different content")
        assigned = self.split_for(physical_match_id)
        if split is not None and split != assigned:
            existing = any(r.physical_match_id == physical_match_id for r in self.records.values())
            if existing:
                raise LeakageError(f"{physical_match_id} is already in {assigned}")
            if split not in SPLITS:
                raise ValueError(f"Unknown split {split}")
            assigned = split
        record = SourceRecord(
            source_id, physical_match_id, str(archive), digest, archive.stat().st_size,
            assigned, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), len(self.records),
            note,
        )
        self.records[source_id] = record
        self.validate()
        self.save()
        return record, True

    # Queries ---------------------------------------------------------------
    def sources(self, split: str | None = None, *, limit_matches: int | None = None
                ) -> list[SourceRecord]:
        """Sources in intake order; ``limit_matches`` keeps the first N physical matches."""
        ordered = sorted(self.records.values(), key=lambda r: r.order)
        if split is not None:
            ordered = [r for r in ordered if r.split == split]
        if limit_matches is None:
            return ordered
        matches: list[str] = []
        for record in ordered:
            if record.physical_match_id not in matches:
                matches.append(record.physical_match_id)
        keep = set(matches[:limit_matches])
        return [r for r in ordered if r.physical_match_id in keep]

    def fingerprint(self, split: str | None = None) -> str:
        items = sorted(f"{r.source_id}:{r.archive_sha256}:{r.split}" for r in self.sources(split))
        return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()[:16]  # noqa: UP012

    def validate(self) -> None:
        seen: dict[str, str] = {}
        for record in self.records.values():
            if record.split not in SPLITS:
                raise ValueError(f"Unknown split {record.split}")
            previous = seen.setdefault(record.physical_match_id, record.split)
            if previous != record.split:
                raise LeakageError(f"{record.physical_match_id} spans {previous}/{record.split}")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "version": "continual_dataset_registry_v1",
            "seed": self.seed,
            "ratios": self.ratios,
            "sources": [asdict(r) for r in sorted(self.records.values(), key=lambda r: r.order)],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def summary(self) -> dict[str, Any]:
        counts: dict[str, dict[str, int]] = {}
        for split in SPLITS:
            records = self.sources(split)
            counts[split] = {
                "sources": len(records),
                "physical_matches": len({r.physical_match_id for r in records}),
            }
        return {"fingerprint": self.fingerprint(), "splits": counts}
