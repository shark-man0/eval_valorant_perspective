"""Round visual projection guards observation gaps and persistent banners."""

from fractions import Fraction

from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.game import observation
from valorant_ai_coach.temporal.round_visual import round_visual_candidates


def observed(second, signals=(), score=None, source="a", epoch="one"):
    sample = freeze_native_sample({
        "source_id": source, "source_sha256": source * 64,
        "acquisition_id": epoch, "native_epoch": epoch,
        "native_pts_tick": second, "native_time_base": "1",
        "frame_size_px": [64, 64], "acquired_frame_sha256": "b" * 64,
        "native_pixel_sha256": "c" * 64,
    })
    return observation(sample=sample, producer="d" * 64, signals=list(signals),
                       raw={}, context={"score": score}, continuity={"decode_ok": True})


def test_positive_buy_to_active_and_result_onset_deduplicate_score():
    rows = [observed(1, ["buy"], [0, 0]), observed(2, [], [0, 0]),
            observed(3, ["active"], [0, 0]), observed(20, ["result"], [0, 0]),
            observed(21, ["result"], [1, 0]), observed(22, ["result"], [1, 0])]
    result = round_visual_candidates(rows)
    assert [(c["kind"], c["candidate_second"]) for c in result["candidates"]] == [
        ("start", 3), ("end", 20)]
    assert result["candidates"][1]["support_cues"] == ["result_display_onset", "score_increment"]
    assert result["formal_outputs"] == 0


def test_missing_hud_and_epoch_reset_do_not_become_boundaries():
    rows = [observed(1, ["buy"]), observed(2), observed(3, epoch="two", signals=["active"]),
            observed(4, epoch="two", signals=["result"])]
    result = round_visual_candidates(rows, origin=Fraction(0))
    assert [c["kind"] for c in result["candidates"]] == ["end"]


def test_score_increment_requires_two_valid_observations():
    rows = [observed(1, score=[3, 2]), observed(2, score=[3, 3]),
            observed(3, score=None), observed(4, score=[9, 0])]
    result = round_visual_candidates(rows)
    assert [(c["kind"], c["candidate_second"]) for c in result["candidates"]] == [
        ("end", 2)]


def test_persistent_result_is_one_candidate_until_next_buy():
    rows = [observed(1, ["result"]), observed(2, ["result"]),
            observed(8, ["result"]), observed(9, ["buy"]),
            observed(10, ["active"]), observed(11, ["result"])]
    result = round_visual_candidates(rows)
    assert [(c["kind"], c["candidate_second"]) for c in result["candidates"]] == [
        ("end", 1), ("start", 10), ("end", 11)]


def test_attach_keeps_existing_application_fields():
    from copy import deepcopy

    from tests.unit.test_development_timeline_application import make_timeline
    from valorant_ai_coach.temporal.application import build_application_timeline
    from valorant_ai_coach.temporal.round_visual import attach_round_visual_candidates

    timeline = make_timeline()
    source = {"video_id": "synthetic", "source_sha256": "a" * 64,
              "physical_match_id": "p"}
    bundle = build_application_timeline(timeline, source=source,
                                        duration=Fraction(7, 2), origin=Fraction(51, 10))
    before = deepcopy(bundle)
    attach_round_visual_candidates(bundle)
    sidecar = bundle.pop("round_visual_candidates")
    for row in bundle["seconds"]:
        row.pop("round_visual_candidates")
    assert bundle == before
    assert sidecar["formal_outputs"] == 0
