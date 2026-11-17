"""TRAIN-only sources and lineage for HUD templates built from recordings.

Templates derived from our own footage (spike header, score digits) must be
built from TRAIN recordings only, so VALIDATION / DEV_COMPARISON /
INDEPENDENT_TEST matches stay unseen. ``train_sources`` enforces that against
the continual-learning dataset registry (#154) and returns the lineage that
the template manifest records: which recordings, which archive bytes, which
registry. Any archive that is not a registered TRAIN recording is refused.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

TRAIN = "TRAIN"
_LEGACY = {"FROZEN_TEST": "DEV_COMPARISON"}


class TemplateSourceRefused(ValueError):
    """An archive is not a registered TRAIN recording."""


@dataclass(frozen=True)
class SourceLineage:
    source_id: str
    split: str
    physical_match_id: str
    source_video_sha256: str
    archive: str
    archive_sha256: str
    video_identity: str  # how the archive was tied to the registered recording


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


def train_sources(registry_path: Path, archives: Sequence[Path], *,
                  video_hashes: Mapping[str, Mapping[str, Any]] | None = None,
                  ) -> tuple[list[SourceLineage], dict[str, Any]]:
    """Check every archive is a TRAIN recording; return per-source lineage.

    An archive is tied to a registry record by its ``video_id``. With
    ``video_hashes`` (video_id -> file_name, size_bytes, sha256 of the original
    recording) the archive's recorded file name and size must also match and
    the original's SHA-256 must equal the registry's ``source_video_sha256``.
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
        identity = "video_id"
        if video_hashes is not None:
            known = video_hashes.get(record["source_id"])
            if (known is None or known.get("file_name") != video["file_name"]
                    or int(known.get("size_bytes", -1)) != int(video["size_bytes"] or -2)
                    or known.get("sha256") != record["source_video_sha256"]):
                refused.append(f"{path.name}: original recording does not match the registry")
                continue
            identity = "video_id+file_name+size+sha256"
        lineage.append(SourceLineage(
            record["source_id"], split, record["physical_match_id"],
            record["source_video_sha256"], path.name, file_sha256(path), identity))
    if refused:
        raise TemplateSourceRefused("template sources must be TRAIN recordings: "
                                    + "; ".join(refused))
    meta = {"registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
            "registry_version": registry.get("version"), "registry_seed": registry.get("seed"),
            "split": TRAIN, "sources": [asdict(entry) for entry in lineage]}
    return lineage, meta
