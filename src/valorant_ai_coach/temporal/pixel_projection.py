"""Exact-native advisory sidecars; no additional state or acquisition lanes."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from copy import deepcopy
from fractions import Fraction
from typing import Any

from .evidence import native_time
from .game import observation


def native_pixel_key(sample: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(sample[k] for k in (
        "source_id", "source_sha256", "native_pts_tick", "native_time_base", "native_pixel_sha256"
    )) + (tuple(sample["frame_size_px"]),)


def attach_pixel_evidence(
    bundle: dict[str, Any], rows: list[dict[str, Any]], *, schema: str, stream_kind: str,
    prefix: str, target_field: str, validate: Callable[[dict[str, Any]], None],
    project: Callable[[list[dict[str, Any]]], dict[str, Any]],
) -> None:
    """Retain every raw epoch, attaching only exact matching current pixels."""
    native: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    for key, frame in bundle["native_frames"].items():
        native[native_pixel_key(frame["sample"])].append(key)
    bins: dict[int, list[dict[str, Any]]] = defaultdict(list)
    links, unmatched = [], []
    seen = set()
    origin = Fraction(bundle["recording"]["native_origin_seconds"])
    for view in bundle["seconds"]:
        view[prefix + "_sample_refs"] = []
    for row in rows:
        expected = observation(
            sample=row["sample"], producer=row["producer_fingerprint"],
            signals=row["signals"], raw=row["raw"], context=row["context"],
            continuity=row["continuity"], map_candidates=row["map_candidates"],
        )
        if (expected != row or row["signals"] or row["map_candidates"]
                or row["raw"].get("schema") != schema
                or row["raw"].get("formal_outputs") != 0
                or row["context"].get("stream_kind") != stream_kind
                or row["sample"]["source_sha256"] != bundle["source"]["source_sha256"]
                or row["sample"]["source_id"] != bundle["source"]["source_id"]):
            raise ValueError("Original same-Source value-only HUD evidence required")
        validate(row)
        identity = row["observation_id"]
        if identity in seen:
            raise ValueError("Duplicate HUD value observation is not independent evidence")
        seen.add(identity)
        existing = bundle["observations"].get(identity)
        if existing is not None and existing != row:
            raise ValueError("Conflicting HUD evidence identity")
        bundle["observations"][identity] = deepcopy(row)
        matches = native.get(native_pixel_key(row["sample"]), [])
        second = int((native_time(row["sample"]) - origin) // 1)
        if (not matches or not 0 <= second < len(bundle["seconds"])
                or row["continuity"].get("decode_ok") is False):
            unmatched.append(identity)
            continue
        bins[second].append(row)
        links.append({"observation_id": identity, "original_sample": deepcopy(row["sample"]),
                      "matched_native_sample_refs": list(matches),
                      "criterion": "exact_Source_PTS_timebase_pixels_dimensions",
                      "independent_confirmation": False, "state_authority": False})
    for second, extra in bins.items():
        view = bundle["seconds"][second]
        ids = sorted(set(view["evidence_refs"]) | {r["observation_id"] for r in extra})
        view[target_field] = project([bundle["observations"][i] for i in ids])
        view["evidence_refs"] = ids
        view[prefix + "_sample_refs"] = [r["sample"]["sample_sha256"] for r in extra]
    bundle[prefix + "_observation_links"] = links
    bundle["unmatched_" + prefix + "_observation_ids"] = unmatched
