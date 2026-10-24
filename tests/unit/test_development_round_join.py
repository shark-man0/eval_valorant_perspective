import copy

import pytest

from valorant_ai_coach.visual.development_round_join import associate_lifecycle_witnesses


def example():
    record = dict(source_id="source", source_sha256="1"*64, native_pts_tick=123,
                  native_time_base="1/60", native_epoch="decode1", acquired_frame_sha256="2"*64,
                  native_pixel_sha256="3"*64, qualification="development_only",
                  ownership={"identity": "UNKNOWN"}, formal_self_position_fact=None)
    witness = dict(source_id="source", source_sha256="1"*64, tick=123, time_base="1/60",
                   epoch="decode1", encoded_sha256="2"*64, pixel_sha256="3"*64,
                   lifecycle_candidate_id="round_candidate", phase_candidate="purchase_witness",
                   qualification="development_only", ownership="UNKNOWN")
    return record, witness


def test_exact_witness_only_does_not_assign_round_or_ownership_or_fill_adjacent_time():
    record, witness = example()
    adjacent = {**record, "native_pts_tick": 124}
    report = associate_lifecycle_witnesses([record, adjacent], [witness])
    assert report["associations"][0]["phase_candidate"] == "purchase_witness"
    assert report["associations"][1]["lifecycle_candidate_id"] is None
    assert all(a["round_id"] is None and a["ownership"] == "UNKNOWN"
               for a in report["associations"])
    assert report["formal_events"] == []


@pytest.mark.parametrize("field,value", [("native_epoch", "decode2"), ("source_id", "other"),
    ("source_sha256", "4"*64), ("native_pixel_sha256", "4"*64),
    ("acquired_frame_sha256", "4"*64), ("native_pts_tick", 124)])
def test_source_pts_epoch_and_frame_content_cannot_be_silently_reassociated(field, value):
    record, witness = example()
    record[field] = value
    result = associate_lifecycle_witnesses([record], [witness])
    assert result["associations"][0]["reason"] == "no_identical_native_witness"


def test_conflicting_candidate_claims_and_missing_native_identity_remain_unknown():
    record, witness = example()
    conflict = {**witness, "lifecycle_candidate_id": "other_candidate"}
    missing = copy.deepcopy(record)
    missing.pop("native_epoch")
    result = associate_lifecycle_witnesses([record, missing], [witness, conflict])
    assert result["reasons"] == {"ambiguous_lifecycle_witness": 1, "native_identity_unavailable": 1}
    assert all(a["lifecycle_candidate_id"] is None for a in result["associations"])


def test_production_or_unqualified_witness_cannot_enter_join():
    record, witness = example()
    witness["ownership"] = "SELF"
    with pytest.raises(ValueError):
        associate_lifecycle_witnesses([record], [witness])
    record["ownership"]["identity"] = "SELF"
    with pytest.raises(ValueError):
        associate_lifecycle_witnesses([record], [])
