"""Incremental registry of private recording archives for continual learning.

Splits:

* ``TRAIN`` / ``VALIDATION``: development data. Models are fitted on TRAIN and
  adopted or rejected on VALIDATION only.
* ``DEV_COMPARISON``: a fixed development set kept for before/after comparison
  across versions. It has been looked at during development, so it is reported
  but never used for adoption decisions and never called an independent test.
* ``INDEPENDENT_TEST``: recordings registered as unexposed. Only the explicit
  independent evaluation reads them; training and gating never do.

Leakage is prevented on the source video, not on the derived archive: every
record carries the SHA-256 of the original recording and a physical match id,
and neither may appear in two splits. Adding a recording never re-splits
earlier ones. The registry stores hashes and decisions only; archives and
videos stay private.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SPLITS = ("TRAIN", "VALIDATION", "DEV_COMPARISON", "INDEPENDENT_TEST")
DEVELOPMENT_SPLITS = ("TRAIN", "VALIDATION", "DEV_COMPARISON")
DEFAULT_RATIOS = {"TRAIN": 0.6, "VALIDATION": 0.2, "DEV_COMPARISON": 0.2}
_LEGACY_SPLITS = {"FROZEN_TEST": "DEV_COMPARISON"}


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
    source_video_sha256: str = ""
    exposure: str = "DEVELOPMENT"  # DEVELOPMENT or UNEXPOSED_AT_REGISTRATION


class LeakageError(ValueError):
    """A video or physical match would appear in more than one split."""


class DatasetRegistry:
    """JSON-backed, append-only registry. ``path`` lives in a private directory."""

    def __init__(self, path: Path, *, seed: str = "continual-v1",
                 ratios: dict[str, float] | None = None) -> None:
        self.path = path
        self.seed = seed
        self.ratios = dict(ratios or DEFAULT_RATIOS)
        if set(self.ratios) != set(DEVELOPMENT_SPLITS) or abs(sum(self.ratios.values()) - 1) > 1e-9:
            raise ValueError("Ratios must cover TRAIN/VALIDATION/DEV_COMPARISON and sum to 1")
        self.records: dict[str, SourceRecord] = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("seed") != seed:
                raise ValueError("Registry seed differs; splits would change")
            self.ratios = {_LEGACY_SPLITS.get(k, k): v for k, v in data["ratios"].items()}
            for item in data["sources"]:
                item["split"] = _LEGACY_SPLITS.get(item["split"], item["split"])
                record = SourceRecord(**item)
                self.records[record.source_id] = record
        self.validate()

    # Split assignment ------------------------------------------------------
    def _existing_split(self, physical_match_id: str, video_sha256: str) -> str | None:
        for record in self.records.values():
            if record.physical_match_id == physical_match_id or (
                    video_sha256 and record.source_video_sha256 == video_sha256):
                return record.split
        return None

    def split_for(self, physical_match_id: str, video_sha256: str = "") -> str:
        existing = self._existing_split(physical_match_id, video_sha256)
        if existing is not None:
            return existing
        bucket = _bucket(physical_match_id, self.seed)
        edge = 0.0
        for split in DEVELOPMENT_SPLITS:
            edge += self.ratios[split]
            if bucket < edge:
                return split
        return DEVELOPMENT_SPLITS[-1]

    def intake(self, source_id: str, physical_match_id: str, archive: Path, *,
               source_video_sha256: str, split: str | None = None, unexposed: bool = False,
               note: str = "") -> tuple[SourceRecord, bool]:
        """Register an archive of one recording. Returns (record, added).

        Re-intake of the same archive is a no-op. A recording or physical match
        that is already registered keeps its split; asking for another split
        raises :class:`LeakageError`. ``unexposed=True`` places a *new* physical
        match in INDEPENDENT_TEST; it is refused for anything already seen.
        """
        if len(source_video_sha256) != 64:
            raise ValueError("source_video_sha256 (SHA-256 of the original recording) is required")
        digest = file_sha256(archive)
        for record in self.records.values():
            if record.archive_sha256 == digest:
                if record.source_id != source_id:
                    raise ValueError(f"Duplicate content: {source_id} == {record.source_id}")
                return record, False
            if record.source_video_sha256 == source_video_sha256 and \
                    record.source_id != source_id:
                raise LeakageError(f"{source_id} is the same recording as {record.source_id}")
        if source_id in self.records:
            raise ValueError(f"{source_id} already registered with different content")
        existing = self._existing_split(physical_match_id, source_video_sha256)
        if unexposed:
            if existing is not None:
                raise LeakageError(f"{physical_match_id} was already registered ({existing}); "
                                   "it cannot be an independent test")
            assigned = "INDEPENDENT_TEST"
        else:
            assigned = self.split_for(physical_match_id, source_video_sha256)
            if split is not None and split != assigned:
                if existing is not None:
                    raise LeakageError(f"{physical_match_id} is already in {assigned}")
                if split not in DEVELOPMENT_SPLITS:
                    raise ValueError(f"Unknown or non-development split {split}")
                assigned = split
        record = SourceRecord(
            source_id, physical_match_id, str(archive), digest, archive.stat().st_size,
            assigned, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), len(self.records),
            note, source_video_sha256,
            "UNEXPOSED_AT_REGISTRATION" if unexposed else "DEVELOPMENT",
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
        items = sorted(f"{r.source_id}:{r.archive_sha256}:{r.source_video_sha256}:{r.split}"
                       for r in self.sources(split))
        return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()[:16]  # noqa: UP012

    def validate(self) -> None:
        by_match: dict[str, str] = {}
        by_video: dict[str, str] = {}
        for record in self.records.values():
            if record.split not in SPLITS:
                raise ValueError(f"Unknown split {record.split}")
            previous = by_match.setdefault(record.physical_match_id, record.split)
            if previous != record.split:
                raise LeakageError(f"{record.physical_match_id} spans {previous}/{record.split}")
            if record.source_video_sha256:
                seen = by_video.setdefault(record.source_video_sha256, record.split)
                if seen != record.split:
                    raise LeakageError(f"video {record.source_video_sha256[:12]} spans splits")
            if record.split == "INDEPENDENT_TEST" and \
                    record.exposure != "UNEXPOSED_AT_REGISTRATION":
                raise LeakageError(f"{record.source_id}: exposed data in INDEPENDENT_TEST")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "version": "continual_dataset_registry_v2",
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
