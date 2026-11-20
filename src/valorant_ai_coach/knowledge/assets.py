"""Private, hash-verified cache of official reference images.

Images are Riot-owned and stay outside Git. The cache is produced by
``scripts/knowledge/fetch_reference_assets.py`` (or imported from a ``.vakb``
browser bundle) and verified against the digest pinned in
``config/game_knowledge/reference_assets_<version>.json``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.resources import resource_path

from .catalog import DEFAULT_VERSION, KNOWLEDGE_DIR

CACHE_ENV = "VALORANT_KNOWLEDGE_CACHE"
_URL_PATTERNS = (
    (re.compile(r"/agents/([0-9a-f-]{36})/abilities/([a-z0-9]+)/displayicon\.png$"), "ability"),
    (re.compile(r"/agents/([0-9a-f-]{36})/([a-z]+)\.png$"), "agent"),
    (re.compile(r"/weapons/([0-9a-f-]{36})/([a-z]+)\.png$"), "weapon"),
    (re.compile(r"/maps/([0-9a-f-]{36})/(displayicon)\.png$"), "map"),
)
_API_SLOTS = {"grenade": "Grenade", "ability1": "Ability1", "ability2": "Ability2",
              "ultimate": "Ultimate", "passive": "Passive"}


class ReferenceAssetsUnavailable(RuntimeError):
    """The private reference image cache is missing or does not verify."""


def default_cache_dir(version: str = DEFAULT_VERSION) -> Path:
    configured = os.environ.get(CACHE_ENV)
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".valorant_ai_coach" / "knowledge" / version


def asset_id_for_url(url: str) -> str | None:
    for pattern, kind in _URL_PATTERNS:
        match = pattern.search(url)
        if match:
            uuid, variant = match.groups()
            if kind == "ability":
                variant = _API_SLOTS.get(variant, variant)
            return f"{kind}:{uuid}:{variant}"
    return None


def content_digest(entries: list[dict[str, Any]]) -> str:
    lines = sorted(f"{entry['url']} {entry['sha256']}" for entry in entries)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def pinned_manifest(version: str = DEFAULT_VERSION) -> dict[str, Any]:
    path = resource_path(f"{KNOWLEDGE_DIR}/reference_assets_{version}.json")
    return dict(json.loads(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    kind: str
    subject: str
    variant: str
    url: str
    path: Path
    sha256: str


class ReferenceAssets:
    """Read-only view over a verified cache directory."""

    def __init__(self, root: Path, records: dict[str, AssetRecord], game_version: str,
                 digest: str) -> None:
        self.root = root
        self.records = records
        self.game_version = game_version
        self.content_digest = digest

    @classmethod
    def load(cls, root: Path | None = None, *, version: str = DEFAULT_VERSION,
             verify_files: bool = True) -> ReferenceAssets:
        root = (root or default_cache_dir(version)).expanduser().resolve()
        index_path = root / "index.json"
        if not index_path.is_file():
            raise ReferenceAssetsUnavailable(
                f"Reference image cache not found at {root}. Run "
                "scripts/knowledge/fetch_reference_assets.py --out <dir> and set "
                f"{CACHE_ENV}=<dir>."
            )
        index = json.loads(index_path.read_text(encoding="utf-8"))
        entries = index["files"]
        digest = content_digest(entries)
        pinned = pinned_manifest(version)["content_digest"]
        if digest != pinned or index.get("content_digest") != digest:
            raise ReferenceAssetsUnavailable(
                f"Reference cache digest {digest} differs from pinned {pinned}"
            )
        records: dict[str, AssetRecord] = {}
        for entry in entries:
            asset_id = asset_id_for_url(entry["url"])
            if asset_id is None:
                continue
            path = (root / entry["path"]).resolve()
            if not path.is_relative_to(root):
                raise ReferenceAssetsUnavailable(f"Cache entry escapes root: {entry['path']}")
            if verify_files:
                if not path.is_file():
                    raise ReferenceAssetsUnavailable(f"Missing cached file {entry['path']}")
                if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                    raise ReferenceAssetsUnavailable(f"Hash mismatch for {entry['path']}")
            records[asset_id] = AssetRecord(
                asset_id, entry["kind"], entry["subject"], entry["variant"], entry["url"],
                path, entry["sha256"],
            )
        return cls(root, records, str(index.get("game_version", version)), digest)

    def has(self, asset_id: str) -> bool:
        return asset_id in self.records

    def image(self, asset_id: str) -> NDArray[np.uint8]:
        """BGRA image for ``asset_id`` (alpha preserved)."""
        return _decode(str(self.records[asset_id].path))

    def ids(self, kind: str) -> tuple[str, ...]:
        return tuple(sorted(i for i, r in self.records.items() if r.kind == kind))


@cache
def _decode(path: str) -> NDArray[np.uint8]:
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ReferenceAssetsUnavailable(f"Cannot decode {path}")
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    elif image.shape[2] == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    result = np.asarray(image, dtype=np.uint8)
    result.setflags(write=False)
    return result


def import_vakb_bundle(bundle: Path, out: Path, *, version: str = DEFAULT_VERSION) -> Path:
    """Unpack a browser ``.vakb`` bundle into a cache directory after hash checks."""
    data = bundle.read_bytes()
    manifest = pinned_manifest(version)["bundle"]
    if hashlib.sha256(data).hexdigest() != manifest["sha256"]:
        raise ReferenceAssetsUnavailable("Bundle hash differs from the pinned manifest")
    first = data.index(b"\n")
    second = data.index(b"\n", first + 1)
    if data[:first] != b"VAKB1":
        raise ReferenceAssetsUnavailable("Not a VAKB1 bundle")
    header = json.loads(data[first + 1:second].decode("utf-8"))
    body = data[second + 1:]
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    for item in header["files"]:
        blob = body[item["offset"]:item["offset"] + item["length"]]
        if hashlib.sha256(blob).hexdigest() != item["sha256"]:
            raise ReferenceAssetsUnavailable(f"Hash mismatch in bundle for {item['url']}")
        subject = re.sub(r"[^a-z0-9]+", "_", item["subject"].casefold()).strip("_")
        variant = re.sub(r"[^a-z0-9]+", "_", item["variant"].casefold()).strip("_")
        relative = Path(item["kind"]) / subject / f"{variant}.png"
        (out / relative).parent.mkdir(parents=True, exist_ok=True)
        (out / relative).write_bytes(blob)
        entries.append({**{k: item[k] for k in ("kind", "subject", "variant", "url", "sha256")},
                        "length": len(blob), "path": relative.as_posix()})
    index = {"format": "valorant_reference_cache_v1", "game_version": header["game_version"],
             "source": "valorant_api_media", "content_digest": content_digest(entries),
             "files": entries}
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), "utf-8")
    return out
