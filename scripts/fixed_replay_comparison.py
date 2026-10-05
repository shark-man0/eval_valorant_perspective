"""Aggregate-only comparisons for fixed replay and adaptive sampling experiments.

Inputs are mappings with ``manifest_sha256``, ``source_sha256`` and a ``frames`` list.
Each frame has an opaque deterministic ``frame_key`` and snapshot fields (either
inline or under ``snapshot``). Values are compared structurally: missing, null,
false, zero, empty string, and empty containers remain distinct.

This module never interprets which behavior is correct. Manual interpretation
tags are caller supplied metadata and default to ``unresolved``.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

INTERPRETATIONS = frozenset(
    {
        "intended_safety_correction",
        "intended_recall_improvement",
        "unexpected_regression",
        "sampling_independent_behavior_change",
        "unresolved",
    }
)
_MISSING = object()


def _frames(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_frames = document.get("frames")
    if not isinstance(raw_frames, Sequence) or isinstance(raw_frames, (str, bytes)):
        raise ValueError("frames must be a sequence")
    result: dict[str, dict[str, Any]] = {}
    for item in raw_frames:
        if not isinstance(item, Mapping):
            raise ValueError("each frame must be a mapping")
        key = item.get("frame_key")
        if not isinstance(key, str) or not key:
            raise ValueError("frame_key must be a non-empty opaque string")
        if key in result:
            raise ValueError("duplicate frame_key")
        nested = item.get("snapshot")
        if nested is not None:
            if not isinstance(nested, Mapping):
                raise ValueError("snapshot must be a mapping")
            snapshot = dict(nested)
        else:
            snapshot = {k: v for k, v in item.items() if k != "frame_key"}
        result[key] = snapshot
    return result


def _validate_hashes(document: Mapping[str, Any]) -> tuple[str, str]:
    manifest = document.get("manifest_sha256")
    source = document.get("source_sha256")
    if not isinstance(manifest, str) or re.fullmatch(r"[0-9a-fA-F]{64}", manifest) is None:
        raise ValueError("manifest_sha256 must be a 64-character SHA-256 hex digest")
    if not isinstance(source, str) or re.fullmatch(r"[0-9a-fA-F]{64}", source) is None:
        raise ValueError("source_sha256 must be a 64-character SHA-256 hex digest")
    return manifest.lower(), source.lower()


def _validate_pair(
    baseline: Mapping[str, Any], current: Mapping[str, Any], *, fixed: bool
) -> tuple[dict, dict]:
    manifest_a, source_a = _validate_hashes(baseline)
    manifest_b, source_b = _validate_hashes(current)
    if source_a != source_b:
        raise ValueError("replay source_sha256 mismatch")
    if fixed and manifest_a != manifest_b:
        raise ValueError("fixed replay manifest_sha256 mismatch")
    return _frames(baseline), _frames(current)


def _get(obj: Mapping[str, Any], key: str) -> Any:
    return obj.get(key, _MISSING)


def _eq(a: Any, b: Any) -> bool:
    if a is _MISSING or b is _MISSING:
        return a is b
    return type(a) is type(b) and a == b


def _label(value: Any) -> str:
    if value is _MISSING:
        return "<missing>"
    raw = str(value)
    if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", raw):
        return raw
    return "value_sha256:" + hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()


def _reader_value_changes(a: Any, b: Any) -> dict[str, int]:
    """Count availability and value changes per reader; None/absence mean unavailable.

    Empty strings and containers, False, and zero are concrete values and remain
    distinct. This preserves a legitimate zero reading while allowing None to
    mean that a reader did not accept a value.
    """
    unavailable_a = a is _MISSING or a is None
    unavailable_b = b is _MISSING or b is None
    result = {"gained": 0, "lost": 0, "changed": 0}
    if unavailable_a and not unavailable_b:
        result["gained"] = 1
    elif not unavailable_a and unavailable_b:
        result["lost"] = 1
    elif not unavailable_a and not unavailable_b and not _eq(a, b):
        result["changed"] = 1
    return result


def _reader_deltas(a: Any, b: Any) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    left = a if isinstance(a, Mapping) else {}
    right = b if isinstance(b, Mapping) else {}
    totals = {"gained": 0, "lost": 0, "changed": 0}
    per_reader: dict[str, dict[str, int]] = {}
    for reader_name in set(left) | set(right):
        delta = _reader_value_changes(
            left.get(reader_name, _MISSING), right.get(reader_name, _MISSING)
        )
        per_reader[_label(reader_name)] = delta
        for key, count in delta.items():
            totals[key] += count
    return totals, per_reader


def _pair_summary(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    primary_left, primary_right = _get(left, "primary_state"), _get(right, "primary_state")
    primary_transitions = Counter()
    if not _eq(primary_left, primary_right):
        primary_transitions[f"{_label(primary_left)}->{_label(primary_right)}"] += 1

    def positive(value: Any) -> bool:
        return isinstance(value, str) and value in {
            "live_first_person",
            "spectator_first_person",
            "remote_control_view",
            "buy_menu_open",
            "expanded_tactical_map",
        }

    def unknown(value: Any) -> bool:
        return (
            value is None
            or value is _MISSING
            or (isinstance(value, str) and value.lower() == "unknown")
        )

    if _eq(primary_left, primary_right):
        behavior = "unchanged"
    elif positive(primary_left) and unknown(primary_right):
        behavior = "positive_to_unknown"
    elif unknown(primary_left) and positive(primary_right):
        behavior = "unknown_to_positive"
    elif (
        not unknown(primary_left)
        and not unknown(primary_right)
        and not positive(primary_left)
        and not positive(primary_right)
    ):
        behavior = "class_to_class"
    else:
        behavior = "state_changed"

    confidence_fields = ("state_confidence", "hud_confidence")
    stripped_left = {k: v for k, v in left.items() if k not in confidence_fields}
    stripped_right = {k: v for k, v in right.items() if k not in confidence_fields}
    confidence_only = stripped_left == stripped_right and any(
        not _eq(_get(left, k), _get(right, k)) for k in confidence_fields
    )
    if confidence_only:
        behavior = "confidence_only"

    evidence_fields = (
        "reader_values",
        "accepted_reader_values",
        "geometry_valid",
        "remote_view_type",
        "relevant_roi_confidences",
        "identity",
        "structures",
        "spectator",
        "evidence",
        "map_result",
        "visual_eligibility",
        "state_flags",
    )
    ownership_changed = not _eq(_get(left, "ownership"), _get(right, "ownership"))
    world_changed = not _eq(_get(left, "world_eligible"), _get(right, "world_eligible"))
    evidence_changed = (
        ownership_changed
        or world_changed
        or any(not _eq(_get(left, k), _get(right, k)) for k in evidence_fields)
        or stripped_left != stripped_right
    )
    if behavior == "unchanged" and evidence_changed:
        behavior = "other_evidence_change"

    readers_left = left.get("reader_values", {})
    readers_right = right.get("reader_values", {})
    reader_delta, reader_deltas = _reader_deltas(readers_left, readers_right)
    identity_left = left.get("identity", {})
    identity_right = right.get("identity", {})
    spectator_left = left.get("spectator", {})
    spectator_right = right.get("spectator", {})
    return {
        "behavior": behavior,
        "primary_transitions": dict(primary_transitions),
        "identity_reason_transitions": _transition(identity_left, identity_right, "reason"),
        "spectator_reason_transitions": _transition(spectator_left, spectator_right, "reason"),
        "reader_values": reader_delta,
        "reader_values_by_reader": reader_deltas,
        "ownership_changed": ownership_changed,
        "world_eligibility_changed": world_changed,
        "confidence_only": confidence_only,
        "other_evidence_changed": evidence_changed,
    }


def _transition(left: Any, right: Any, field: str) -> dict[str, int]:
    left_mapping = left if isinstance(left, Mapping) else {}
    right_mapping = right if isinstance(right, Mapping) else {}
    a, b = _get(left_mapping, field), _get(right_mapping, field)
    return {} if _eq(a, b) else {f"{_label(a)}->{_label(b)}": 1}


def _aggregate(pairs: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]]) -> dict[str, Any]:
    behaviors = Counter()
    primary = Counter()
    identity_reasons = Counter()
    spectator_reasons = Counter()
    reader = Counter()
    readers_by_name: dict[str, Counter] = {}
    ownership = world = confidence_only = other_evidence = 0
    for left, right in pairs:
        item = _pair_summary(left, right)
        behaviors[item["behavior"]] += 1
        primary.update(item["primary_transitions"])
        identity_reasons.update(item["identity_reason_transitions"])
        spectator_reasons.update(item["spectator_reason_transitions"])
        reader.update(item["reader_values"])
        for name, changes in item["reader_values_by_reader"].items():
            readers_by_name.setdefault(name, Counter()).update(changes)
        ownership += item["ownership_changed"]
        world += item["world_eligibility_changed"]
        confidence_only += item["confidence_only"]
        other_evidence += item["other_evidence_changed"]
    return {
        "paired_frames": len(pairs),
        "behavior_counts": dict(behaviors),
        "primary_state_transitions": dict(primary),
        "identity_reason_transitions": dict(identity_reasons),
        "spectator_reason_transitions": dict(spectator_reasons),
        "reader_value_changes": {k: reader[k] for k in ("gained", "lost", "changed")},
        "reader_value_changes_by_reader": {
            name: {k: counts[k] for k in ("gained", "lost", "changed")}
            for name, counts in readers_by_name.items()
        },
        "ownership_changes": ownership,
        "world_eligibility_changes": world,
        "confidence_only_changes": confidence_only,
        "other_evidence_changes": other_evidence,
    }


def _metadata(
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
    interpretation: str | None,
) -> dict[str, str]:
    tag = interpretation or "unresolved"
    if tag not in INTERPRETATIONS:
        raise ValueError("unsupported manual interpretation")
    baseline_manifest, source = _validate_hashes(baseline)
    current_manifest, current_source = _validate_hashes(current)
    if source != current_source:
        raise ValueError("replay source_sha256 mismatch")
    return {
        "baseline_manifest_sha256": baseline_manifest,
        "current_manifest_sha256": current_manifest,
        "source_sha256": source,
        "interpretation": tag,
    }


def compare_replays(
    baseline: Mapping[str, Any], current: Mapping[str, Any], *, interpretation: str | None = None
) -> dict[str, Any]:
    """Compare identical frozen-manifest/source replay sets using aggregate counts only."""
    old, new = _validate_pair(baseline, current, fixed=True)
    if old.keys() != new.keys():
        raise ValueError("fixed replay frame key sets must match")
    pairs = [(old[key], new[key]) for key in old]
    return {"metadata": _metadata(baseline, current, interpretation), **_aggregate(pairs)}


def compare_adaptive_sampling(
    baseline: Mapping[str, Any], current: Mapping[str, Any], *, interpretation: str | None = None
) -> dict[str, Any]:
    """Compare common sampled frames and report added/removed locator counts only."""
    old, new = _validate_pair(baseline, current, fixed=False)
    common = old.keys() & new.keys()
    removed = old.keys() - new.keys()
    added = new.keys() - old.keys()
    return {
        "metadata": _metadata(baseline, current, interpretation),
        "sampling": {
            "common_frames": len(common),
            "removed_frames": len(removed),
            "added_frames": len(added),
        },
        "common_frame_behavior": _aggregate([(old[k], new[k]) for k in common]),
        "removed_sample_behavior": _aggregate([(old[k], {}) for k in removed]),
        "added_sample_behavior": _aggregate([({}, new[k]) for k in added]),
    }
