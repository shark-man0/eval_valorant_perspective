"""Native-pool guards for development-only Map score diagnostics."""

from copy import deepcopy

from valorant_ai_coach.temporal.application import _exact_map_ui_rows


def example():
    sample = {"source_sha256": "a" * 64, "sample_sha256": "b" * 64}
    pool = [{"marker": "first"}, {"marker": "second"}]
    packet = {
        "sample": sample,
        "map_candidates": pool,
        "raw": {
            "schema": "map_consumer_provisional_v1",
            "ui": {"rows": [{"candidate_index": 0, "score": 0.9}]},
        },
    }
    frame = {"sample": sample, "observation_ids": ["map"], "map": {"candidates": pool}}
    return frame, {"map": packet}


def test_exact_single_packet_supplies_its_own_local_index_scores():
    frame, observations = example()
    before = deepcopy(observations)
    assert _exact_map_ui_rows(frame, observations) == [{"candidate_index": 0, "score": 0.9}]
    assert observations == before


def test_alias_other_source_or_multiple_packets_do_not_supply_local_indices():
    for field in ("sample_sha256", "source_sha256"):
        frame, observations = example()
        observations["map"] = deepcopy(observations["map"])
        observations["map"]["sample"][field] = "c" * 64
        assert _exact_map_ui_rows(frame, observations) is None
    frame, observations = example()
    observations["second"] = deepcopy(observations["map"])
    frame["observation_ids"].append("second")
    assert _exact_map_ui_rows(frame, observations) is None


def test_reordered_pool_or_non_map_packet_cannot_reuse_scores():
    frame, observations = example()
    frame["map"]["candidates"] = list(reversed(frame["map"]["candidates"]))
    assert _exact_map_ui_rows(frame, observations) is None
    frame, observations = example()
    observations["map"]["raw"]["schema"] = "hud"
    assert _exact_map_ui_rows(frame, observations) is None
