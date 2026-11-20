"""Bind private Map training crops to exact native observation IDs."""

from __future__ import annotations

import hashlib

from valorant_ai_coach.temporal.evidence import freeze_native_sample, is_sha
from valorant_ai_coach.temporal.replay import file_sha, read_json

SCHEMA = "map_cnn_crop_lineage_v1"
CATEGORIES = {
    "positive": {"recorder_weak"},
    "negative": {"competing_peak", "nonrecorder_region"},
    "background": {"empty_background_weak"},
}


def load_crop_lineage(path, expected, source, arrays):
    """Reject crop swaps, unbound samples and unverifiable frame provenance."""
    if file_sha(path) != expected:
        raise ValueError("Map training lineage hash mismatch")
    lineage = read_json(path)
    if (lineage.get("schema") != SCHEMA or lineage["source_sha256"] != source
            or not is_sha(lineage.get("native_receipt_sha256"))):
        raise ValueError("Map training lineage source mismatch")
    frames = {
        key: freeze_native_sample(sample) for key, sample in lineage["samples"].items()
    }
    if any(sample["sample_sha256"] != key or sample["source_sha256"] != source
           for key, sample in frames.items()):
        raise ValueError("Map training lineage contains a different native observation")
    seen = set()
    for name, allowed_categories in CATEGORIES.items():
        for patch, item in zip(arrays[name], lineage["rows"][name], strict=True):
            key, role = item["sample_sha256"], item["label"]
            x, y = item["center"]
            sample = frames.get(key)
            ids = item["timeline_observation_ids"]
            if (
                sample is None or role not in allowed_categories
                or not isinstance(ids, list) or not all(is_sha(ref) for ref in ids)
                or not 12 <= x < sample["frame_size_px"][0] - 12
                or not 12 <= y < sample["frame_size_px"][1] - 12
                or (key, x, y) in seen
                or hashlib.sha256(patch.tobytes()).hexdigest() != item["patch_sha256"]
            ):
                raise ValueError("Map training crop bytes or native lineage differ")
            seen.add((key, x, y))
    return lineage
