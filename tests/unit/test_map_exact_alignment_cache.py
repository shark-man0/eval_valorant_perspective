from types import SimpleNamespace

import numpy as np
import pytest

from valorant_ai_coach.temporal.map_exact_alignment_cache import ExactAlignmentCache


def test_exact_fit_uses_only_the_same_frame_and_projector(tmp_path):
    calls = []

    def inspect_exact(image):
        calls.append(image)
        return {"raw": {"map_name_candidates": [], "formal_outputs": 0}}

    projector = SimpleNamespace(fingerprint="config1", inspect_exact=inspect_exact)
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    sample = {"sample_sha256": "sample1"}
    cache = ExactAlignmentCache(projector, tmp_path)
    first = cache.inspect(image, sample)
    first["map_name_candidates"].append("mutation")
    second = ExactAlignmentCache(projector, tmp_path)
    assert second.inspect(image, sample)["map_name_candidates"] == []
    assert second.hits == 1 and len(calls) == 1
    second.inspect(image, {"sample_sha256": "sample2"})
    projector.fingerprint = "config2"
    second.inspect(image, sample)
    assert len(calls) == 3
    for entry in tmp_path.glob("*.json"):
        entry.write_text('{"key":"bad"}', encoding="utf-8")
    with pytest.raises(ValueError, match="cache entry changed"):
        second.inspect(image, sample)
