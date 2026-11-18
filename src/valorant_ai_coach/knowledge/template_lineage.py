"""TRAIN-only sources and lineage for HUD templates built from recordings.

Templates derived from our own footage (spike header, score digits, magazine
digits) must be built from TRAIN recordings only, so VALIDATION /
DEV_COMPARISON / INDEPENDENT_TEST matches stay unseen. ``train_sources``
checks every archive four ways before a builder may read it:

1. dataset registry (#154): the archive's ``video_id`` is a registered source
   whose split is TRAIN;
2. archive bytes: the archive file's SHA-256 and size equal the registry's
   ``archive_sha256`` / ``archive_bytes`` (a re-packed or extended archive is
   refused even when it carries the same recording);
3. recording catalog (the single private registry, #62): the recording with the
   registry's ``source_video_sha256`` exists, is authorised for development,
   is not held out for independent evaluation, and its write-once ``learning``
   sub-split is TRAIN for the same registry source and physical match;
4. original recording: the file name and size the archive was cut from equal
   the catalog's verified original location (and, when ``video_hashes`` is
   given, an independently computed SHA-256 of that original).

The returned meta is what the template manifest records as its lineage.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Protocol

TRAIN = "TRAIN"
_LEGACY = {"FROZEN_TEST": "DEV_COMPARISON"}
IDENTITY = "registry+archive_sha256+catalog_learning+original_name_size"
IDENTITY_HASHED = IDENTITY + "+original_sha256"


class TemplateSourceRefused(ValueError):
    """An archive is not a verified, registered TRAIN recording."""


class CatalogRecording(Protocol):
    recording_id: str
    source_sha256: str
    size_bytes: int
    physical_match_id: str
    locations: dict[str, dict[str, Any]]
    learning: dict[str, Any]

    @property
    def development_authorised(self) -> bool: ...

    @property
    def independent_until_opened(self) -> bool: ...


class CatalogState(Protocol):
    head: str | None

    def by_sha(self, sha: str) -> Any: ...


class Catalog(Protocol):
    state: CatalogState


@dataclass(frozen=True)
class SourceLineage:
    source_id: str
    split: str
    physical_match_id: str
    source_video_sha256: str
    archive: str
    archive_sha256: str
    catalog_recording_id: str
    catalog_learning_origin: str
    original_file_name: str
    original_size_bytes: int
    video_identity: str  # which checks tied the archive to the recording


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_video(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        index = json.loads(archive.read("index.json").decode("utf-8"))
    return {"video_id": index.get("video_id"), "file_name": index.get("file_name"),
            "size_bytes": index.get("size_bytes")}


def _base_name(path: str) -> str:
    return (PureWindowsPath(path) if "\\" in path else PurePosixPath(path)).name


def _catalog_problem(record: Mapping[str, Any], recording: CatalogRecording | None,
                     video: Mapping[str, Any]) -> str | None:
    if recording is None:
        return "recording is not in the catalog"
    if not recording.development_authorised:
        return f"catalog {recording.recording_id} is not authorised for development"
    if recording.independent_until_opened:
        return f"catalog {recording.recording_id} is held out for independent evaluation"
    learning = recording.learning or {}
    if _LEGACY.get(str(learning.get("split")), learning.get("split")) != TRAIN:
        return f"catalog learning split is {learning.get('split') or 'unset'}"
    if (learning.get("registry_source_id") != record["source_id"]
            or learning.get("registry_physical_match_id") != record["physical_match_id"]):
        return "catalog learning split belongs to another registry source"
    original = recording.locations.get("original") or {}
    name = _base_name(str(original.get("path", "")))
    if (name != video["file_name"] or int(recording.size_bytes) != int(video["size_bytes"] or -1)
            or int(original.get("size_bytes", -2)) != int(recording.size_bytes)):
        return "archive was not cut from the catalog's original recording"
    return None


def train_sources(registry_path: Path, archives: Sequence[Path], *, catalog: Catalog,
                  video_hashes: Mapping[str, Mapping[str, Any]] | None = None,
                  ) -> tuple[list[SourceLineage], dict[str, Any]]:
    """Check every archive is a verified TRAIN recording; return per-source lineage.

    ``catalog`` is a loaded ``recordings.catalog.RecordingCatalog`` (its journal
    replay is the integrity check). ``video_hashes`` (video_id -> file_name,
    size_bytes, sha256 of the original) adds an independent hash of the original.
    """
    registry_bytes = registry_path.read_bytes()
    registry = json.loads(registry_bytes.decode("utf-8"))
    records = {row["source_id"]: row for row in registry["sources"]}
    lineage: list[SourceLineage] = []
    refused: list[str] = []
    for path in archives:
        video = _archive_video(path)
        record = records.get(str(video["video_id"]))
        if record is None:
            refused.append(f"{path.name}: not registered")
            continue
        split = _LEGACY.get(record["split"], record["split"])
        if split != TRAIN:
            refused.append(f"{path.name}: {record['source_id']} is {split}")
            continue
        archive_sha = file_sha256(path)
        if (archive_sha != record.get("archive_sha256")
                or path.stat().st_size != int(record.get("archive_bytes", path.stat().st_size))):
            refused.append(f"{path.name}: archive bytes differ from the registry")
            continue
        recording = catalog.state.by_sha(record["source_video_sha256"])
        problem = _catalog_problem(record, recording, video)
        if problem is not None:
            refused.append(f"{path.name}: {problem}")
            continue
        assert recording is not None
        if video_hashes is not None:
            known = video_hashes.get(record["source_id"])
            if (known is None or known.get("file_name") != video["file_name"]
                    or int(known.get("size_bytes", -1)) != int(video["size_bytes"] or -2)
                    or known.get("sha256") != record["source_video_sha256"]):
                refused.append(f"{path.name}: original recording does not match the registry")
                continue
        identity = IDENTITY_HASHED if video_hashes is not None else IDENTITY
        lineage.append(SourceLineage(
            record["source_id"], split, record["physical_match_id"],
            record["source_video_sha256"], path.name, archive_sha,
            recording.recording_id, str(recording.learning.get("origin", "")),
            str(video["file_name"]), int(video["size_bytes"]), identity))
    if refused:
        raise TemplateSourceRefused("template sources must be verified TRAIN recordings: "
                                    + "; ".join(refused))
    meta = {"registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
            "registry_version": registry.get("version"), "registry_seed": registry.get("seed"),
            "catalog_journal_head": catalog.state.head,
            "split": TRAIN, "sources": [asdict(entry) for entry in lineage]}
    return lineage, meta
