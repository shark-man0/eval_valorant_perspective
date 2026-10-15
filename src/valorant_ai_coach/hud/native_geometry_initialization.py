"""Immutable geometry-only reference binding for qualified native transport.

The reference image remains available until Package/Trace publication finishes.
It never enters the current epoch's observations or lifecycle tracker.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast

from valorant_ai_coach.video.native import NativeSourceFrame

from .global_lifecycle import GlobalLifecycleQualification, global_recognizer_fingerprint
from .native_system_input import calibration_prefix_provenance
from .unedited_input import UneditedInputContract


def _first_identity(frame: NativeSourceFrame) -> dict[str, Any]:
    return {
        "source_video_sha256": frame.source_video_sha256,
        "source_epoch": frame.source_epoch,
        "source_pts_ticks": frame.pts_ticks,
        "source_time_base": str(frame.time_base),
        "source_pts_sec": frame.time_sec,
        "source_pixel_sha256": frame.pixel_sha256,
    }


@dataclass(frozen=True)
class NativeGeometryInitialization:
    prefix: NativeSourceFrame
    first: NativeSourceFrame
    context_json: str

    @classmethod
    def bind(
        cls,
        prefix: NativeSourceFrame,
        first: NativeSourceFrame,
        qualification: GlobalLifecycleQualification,
        contract: UneditedInputContract,
        producer_fingerprint: str,
    ) -> NativeGeometryInitialization:
        context = cls._context(prefix, first, qualification, contract, producer_fingerprint)
        return cls(prefix, first, json.dumps(context, sort_keys=True, separators=(",", ":")))

    @staticmethod
    def _context(
        prefix: NativeSourceFrame,
        first: NativeSourceFrame,
        qualification: GlobalLifecycleQualification,
        contract: UneditedInputContract,
        producer_fingerprint: str,
    ) -> dict[str, Any]:
        reference = calibration_prefix_provenance(prefix, first)
        if (
            contract.source_video_sha256 != first.source_video_sha256
            or qualification.recognizer_fingerprint != global_recognizer_fingerprint()
        ):
            raise ValueError("geometry initialization requires current source/code qualification")
        return {
            "scope": "geometry_only_reference_v1",
            "reference": {**reference, "source_epoch": prefix.source_epoch},
            "window_first": _first_identity(first),
            "input_contract_sha256": contract.fingerprint,
            "profile_fingerprint": qualification.profile_fingerprint,
            "recognizer_fingerprint": qualification.recognizer_fingerprint,
            "qualification_sha256": qualification.report_sha256,
            "producer_fingerprint": producer_fingerprint,
        }

    @property
    def observation_fingerprint(self) -> str:
        return hashlib.sha256(self.context_json.encode("utf-8")).hexdigest()

    def verify(
        self,
        qualification: GlobalLifecycleQualification,
        contract: UneditedInputContract,
        first_row: dict[str, Any] | None = None,
        *,
        producer_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        saved = cast(dict[str, Any], json.loads(self.context_json))
        if not isinstance(saved, dict) or not isinstance(saved.get("producer_fingerprint"), str):
            raise ValueError("invalid native geometry initialization context")
        producer = (
            saved["producer_fingerprint"]
            if producer_fingerprint is None
            else (producer_fingerprint)
        )
        expected = self.bind(self.prefix, self.first, qualification, contract, producer)
        first_changed = first_row is not None and any(
            first_row.get(key) != value for key, value in _first_identity(self.first).items()
        )
        if self.context_json != expected.context_json or first_changed:
            raise ValueError("native geometry initialization binding changed")
        return saved


def attest_geometry_initialization(
    events: Sequence[dict[str, Any]],
    initialization: NativeGeometryInitialization | None,
    rows: Sequence[dict[str, Any]],
    qualification: GlobalLifecycleQualification,
    contract: UneditedInputContract,
) -> tuple[dict[str, Any], ...]:
    """Re-read the reference before publishing/replaying its producer output."""
    if initialization is None:
        if any("geometry_initialization_sha256" in row for row in rows):
            raise ValueError("native geometry initialization missing from transport")
        return tuple(events)
    if not rows:
        raise ValueError("geometry initialization requires native window")
    context = initialization.verify(qualification, contract, rows[0])
    if any(
        row.get("input_fingerprint") != initialization.observation_fingerprint
        or row.get("geometry_initialization_sha256") != initialization.observation_fingerprint
        for row in rows
    ):
        raise ValueError("native observations differ from geometry initialization")
    enriched = deepcopy(tuple(events))
    for event in enriched:
        event["attributes"]["evidence_provenance"]["geometry_initialization"] = deepcopy(context)
    return enriched
