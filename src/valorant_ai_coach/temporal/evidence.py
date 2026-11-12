"""Development native evidence. Hashes bind records, never semantic truth.

freeze_native_sample is selectively adapted from PR109 259a051, rather than
importing the marker recognizer or either supplier's game-state machine.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def is_sha(value: Any) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


def freeze_native_sample(record: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "source_id",
        "source_sha256",
        "acquisition_id",
        "native_epoch",
        "native_pts_tick",
        "native_time_base",
        "acquired_frame_sha256",
        "native_pixel_sha256",
        "frame_size_px",
    )
    sample = {k: record.get(k) for k in fields}
    size = sample["frame_size_px"]
    if (
        not isinstance(size, list)
        or len(size) != 2
        or any(type(n) is not int or n <= 0 for n in size)
        or not all(
            is_sha(sample[k])
            for k in ("source_sha256", "acquired_frame_sha256", "native_pixel_sha256")
        )
        or not all(
            isinstance(sample[k], str) and sample[k]
            for k in ("source_id", "acquisition_id", "native_epoch")
        )
        or sample["acquisition_id"] != sample["native_epoch"]
        or type(sample["native_pts_tick"]) is not int
        or not isinstance(sample["native_time_base"], str)
    ):
        raise ValueError("Exact native source/acquisition/frame identity required")
    try:
        base = Fraction(sample["native_time_base"])
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Positive canonical rational time base required") from exc
    if base <= 0 or str(base) != sample["native_time_base"]:
        raise ValueError("Positive canonical rational time base required")
    sample["sample_sha256"] = digest(sample)
    if "sample_sha256" in record and record["sample_sha256"] != sample["sample_sha256"]:
        raise ValueError("Native sample digest mismatch")
    return sample


def native_time(sample: dict[str, Any]) -> Fraction:
    return Fraction(sample["native_pts_tick"]) * Fraction(sample["native_time_base"])


def source_scope(sample: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(sample[k])
        for k in (
            "source_id",
            "source_sha256",
            "acquisition_id",
            "native_epoch",
            "native_time_base",
            "frame_size_px",
        )
    )
