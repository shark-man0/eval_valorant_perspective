"""Explicit source-specific user assurance, separate from image qualification."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UneditedInputContract:
    source_video_sha256: str
    assurance_provenance: str
    fingerprint: str

    @classmethod
    def load(cls, path: Path, *, source_video_sha256: str) -> UneditedInputContract:
        content = path.read_bytes()
        value = json.loads(content)
        claims = {
            "no_user_edit", "no_intentional_frame_deletion_join_or_reorder",
            "no_intentional_speed_change", "scene_preserving_edit_excluded",
        }
        if (
            not isinstance(value, dict)
            or set(value) != claims | {
                "schema_version", "source_video_sha256", "assurance_provenance",
            }
            or value.get("schema_version") != 1
            or type(value.get("schema_version")) is not int
            or re.fullmatch(r"[0-9a-f]{64}", source_video_sha256) is None
            or value.get("source_video_sha256") != source_video_sha256
            or any(value.get(key) is not True for key in claims)
            or not isinstance(value.get("assurance_provenance"), str)
            or not value["assurance_provenance"].strip()
        ):
            raise ValueError("explicit matching unedited input assurance required")
        return cls(source_video_sha256, value["assurance_provenance"],
                   hashlib.sha256(content).hexdigest())
