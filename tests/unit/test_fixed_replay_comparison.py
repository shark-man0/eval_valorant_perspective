"""Aggregate contract tests for fixed replay and adaptive sampling comparison."""

from __future__ import annotations

import json

import pytest

from scripts.fixed_replay_comparison import compare_adaptive_sampling, compare_replays

MANIFEST = "a" * 64
SOURCE = "b" * 64


def doc(frames, manifest=MANIFEST, source=SOURCE):
    return {"manifest_sha256": manifest, "source_sha256": source, "frames": frames}


def frame(key, **snapshot):
    return {"frame_key": key, **snapshot}


def test_fixed_comparison_accounts_for_every_frame_and_parallel_dimensions():
    baseline = doc(
        [
            frame(
                "x1",
                primary_state="live_first_person",
                state_confidence=0.8,
                ownership=True,
                world_eligible=True,
                reader_values={"health": 100},
            ),
            frame("x2", primary_state="unknown", identity={"reason": "old"}),
            frame("x3", primary_state="live_first_person", spectator={"reason": "clear"}),
            frame("x4", primary_state="A", ownership=False),
            frame("x5", primary_state="live_first_person", reader_values={"hp": 10, "ammo": 3}),
        ]
    )
    current = doc(
        [
            frame(
                "x1",
                primary_state="live_first_person",
                state_confidence=0.9,
                ownership=True,
                world_eligible=True,
                reader_values={"health": 100},
            ),
            frame("x2", primary_state="live_first_person", identity={"reason": "new"}),
            frame("x3", primary_state="live_first_person", spectator={"reason": "occluded"}),
            frame("x4", primary_state="B", ownership=True),
            frame("x5", primary_state="live_first_person", reader_values={"hp": 11, "reserve": 4}),
        ]
    )
    result = compare_replays(baseline, current)
    assert sum(result["behavior_counts"].values()) == 5
    assert result["behavior_counts"] == {
        "confidence_only": 1,
        "unknown_to_positive": 1,
        "other_evidence_change": 2,
        "class_to_class": 1,
    }
    assert result["primary_state_transitions"] == {"unknown->live_first_person": 1, "A->B": 1}
    assert result["identity_reason_transitions"] == {"old->new": 1}
    assert result["spectator_reason_transitions"] == {"clear->occluded": 1}
    assert result["ownership_changes"] == 1
    assert result["reader_value_changes_by_reader"]["hp"] == {"gained": 0, "lost": 0, "changed": 1}
    assert result["reader_value_changes_by_reader"]["ammo"]["lost"] == 1
    assert result["reader_value_changes_by_reader"]["reserve"]["gained"] == 1


def test_values_preserve_missing_null_false_zero_and_empty_distinctions():
    values = [None, False, 0, "", [], {}]
    baseline = doc([frame(f"f{i}", primary_state=value) for i, value in enumerate(values)])
    current = doc([frame(f"f{i}", primary_state=values[-i - 1]) for i in range(len(values))])
    output = compare_replays(baseline, current)
    assert output["behavior_counts"].get("unchanged", 0) == 0
    assert sum(output["behavior_counts"].values()) == len(values)


def test_confidence_only_does_not_require_equal_numeric_type():
    a = doc(
        [frame("f", primary_state="live_first_person", state_confidence=0, hud_confidence=None)]
    )
    b = doc(
        [frame("f", primary_state="live_first_person", state_confidence=False, hud_confidence=None)]
    )
    assert compare_replays(a, b)["behavior_counts"] == {"confidence_only": 1}


def test_production_primary_states_and_null_reader_values_use_acceptance_semantics():
    before = doc(
        [
            frame("positive", primary_state="live_first_person"),
            frame(
                "reader",
                primary_state="live_first_person",
                reader_values={"hp": None, "ammo": 0, "armor": False},
            ),
        ]
    )
    after = doc(
        [
            frame("positive", primary_state="unknown"),
            frame(
                "reader",
                primary_state="live_first_person",
                reader_values={"hp": 100, "ammo": None, "armor": 0},
            ),
        ]
    )
    result = compare_replays(before, after)
    assert result["behavior_counts"]["positive_to_unknown"] == 1
    assert result["reader_value_changes"] == {"gained": 1, "lost": 1, "changed": 1}
    assert result["reader_value_changes_by_reader"] == {
        "hp": {"gained": 1, "lost": 0, "changed": 0},
        "ammo": {"gained": 0, "lost": 1, "changed": 0},
        "armor": {"gained": 0, "lost": 0, "changed": 1},
    }


def test_fixed_replay_rejects_duplicate_keys_sets_or_hashes():
    good = doc([frame("f", primary_state="unknown")])
    with pytest.raises(ValueError, match="duplicate frame_key"):
        compare_replays(doc([frame("f"), frame("f")]), good)
    with pytest.raises(ValueError, match="key sets"):
        compare_replays(good, doc([frame("g")]))
    with pytest.raises(ValueError, match="manifest_sha256"):
        compare_replays(good, doc([frame("f")], manifest="c" * 64))
    with pytest.raises(ValueError, match="64-character"):
        compare_replays(doc([frame("f")], source="C:\\private\\video.mp4"), good)


def test_adaptive_sampling_pairs_common_frames_and_allows_manifest_change():
    old = doc(
        [
            frame("same", primary_state="unknown"),
            frame("removed", primary_state="live_first_person"),
        ]
    )
    new = doc(
        [
            frame("same", primary_state="live_first_person"),
            frame("added", primary_state="live_first_person"),
        ],
        manifest="c" * 64,
    )
    result = compare_adaptive_sampling(old, new)
    assert result["sampling"] == {"common_frames": 1, "removed_frames": 1, "added_frames": 1}
    assert result["metadata"]["baseline_manifest_sha256"] == MANIFEST
    assert result["metadata"]["current_manifest_sha256"] == "c" * 64
    assert result["common_frame_behavior"]["behavior_counts"] == {"unknown_to_positive": 1}
    assert result["removed_sample_behavior"]["paired_frames"] == 1
    assert result["added_sample_behavior"]["paired_frames"] == 1
    with pytest.raises(ValueError, match="source_sha256"):
        compare_adaptive_sampling(old, doc([frame("same")], source="c" * 64))


def test_private_locators_and_free_text_never_appear_in_summary():
    secret_path = r"C:\\private\\session-42\\frame.png"
    result = compare_replays(
        doc([frame(secret_path, primary_state="A", identity={"reason": secret_path})]),
        doc([frame(secret_path, primary_state="B", identity={"reason": secret_path + "2"})]),
    )
    text = json.dumps(result)
    assert secret_path not in text
    assert "frame.png" not in text
    assert result["metadata"]["interpretation"] == "unresolved"
    assert (
        compare_replays(
            doc([frame("opaque", primary_state="unknown")]),
            doc([frame("opaque", primary_state="live_first_person")]),
            interpretation="intended_safety_correction",
        )["metadata"]["interpretation"]
        == "intended_safety_correction"
    )
    with pytest.raises(ValueError, match="manual interpretation"):
        compare_replays(doc([frame("opaque")]), doc([frame("opaque")]), interpretation="automatic")

