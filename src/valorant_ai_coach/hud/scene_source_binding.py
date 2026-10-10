"""Immutable file binding for the image-only source acquisition input.

Binding assets does not qualify their world labels, continuity or UI evidence.
Only explicitly configured source profiles participate in the HUD fingerprint.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .scene_references import WorldDomainBootstrap, scene_asset_sha256


@dataclass(frozen=True, slots=True)
class SceneSourceBinding:
    profile_path: Path
    profile_sha256: str
    assets: tuple[tuple[str, str], ...]

    @classmethod
    def load(cls, path: Path) -> SceneSourceBinding:
        path = path.resolve()
        raw_bytes = path.read_bytes()
        raw = json.loads(raw_bytes)
        # Use the same decoded-pixel, reviewed-domain and path validation as the
        # actual acquisition input. A hash alone cannot validate this contract.
        loader = WorldDomainBootstrap(path)
        binding = cls(
            path,
            hashlib.sha256(raw_bytes).hexdigest(),
            tuple(sorted({(entry["asset"], entry["asset_sha256"])
                          for entry in raw["references"]})),
        )
        if loader.references.profile_sha256 != binding.profile_sha256:
            raise ValueError("scene source profile changed during loading")
        binding.verify()
        return binding

    def verify(self) -> None:
        if scene_asset_sha256(self.profile_path) != self.profile_sha256:
            raise ValueError("scene source profile changed after binding")
        root = self.profile_path.parent
        for relative, expected in self.assets:
            asset = (root / relative).resolve()
            if not asset.is_relative_to(root) or scene_asset_sha256(asset) != expected:
                raise ValueError("scene source asset changed after binding")

    def fingerprint(self) -> str:
        self.verify()
        # Absolute host paths never participate: a byte-identical relative
        # profile and its assets retain the same binding on Windows and Pi.
        payload = ["scene-source-binding-v1", self.profile_sha256, self.assets]
        return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()
