"""Contract tests for opt-in, post-inference Round and return candidates."""

import pytest

from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample
from valorant_ai_coach.temporal.game import DevelopmentGameTimeline, observation


def row(tick, signals=(), *, source="a", epoch="e", score=None, timer=None, weak_self=False):
    sample = freeze_native_sample({
        "source_id": source,
        "source_sha256": source * 64,
        "acquisition_id": epoch,
        "native_epoch": epoch,
        "native_pts_tick": tick,
        "native_time_base": "1",
        "acquired_frame_sha256": digest([source, epoch, tick]),
        "native_pixel_sha256": digest([source, tick]),
        "frame_size_px": [1920, 1080],
    })
    if weak_self:
        return observation(
            sample=sample, producer="c" * 64, signals=[], raw={"camera_hypothesis": "SELF"},
            context={"unqualified_view_model": True},
        )
    context = {}
    if score is not None:
        context["score"] = score
    if timer is not None:
        context["timer_seconds"] = timer
    return observation(sample=sample, producer="b" * 64, signals=list(signals),
                       raw={}, context=context)


def replay(rows, **flags):
    engine = DevelopmentGameTimeline(**flags)
    for item in rows:
        engine.add(item)
    return engine.rebuild()


def return_rows(*, return_tick=9, return_source="a", return_epoch="e",
                tail_score=None, return_score=None, tail_signals=()):
    rows = [row(0, ["buy", "owner_hud"]), row(1, ["active", "owner_hud"]),
            row(2, ["spectator", "recorder_elimination_display"]),
            row(3, ["spectator"])]
    rows += [row(t) for t in range(4, return_tick)]
    rows.append(row(6, tail_signals, score=tail_score))
    rows += [row(t, weak_self=True) for t in range(return_tick)]
    rows.append(row(return_tick, ["buy", "owner_hud"], source=return_source,
                    epoch=return_epoch, score=return_score))
    rows.append(row(return_tick, source=return_source, epoch=return_epoch, weak_self=True))
    return rows


def test_return_tail_is_unqualified_candidate_and_disabled_by_default():
    rows = return_rows()
    baseline = replay(rows)
    revised = replay(rows, return_display_tail=True)
    before = next(f for f in baseline["frames"] if f["sample"]["native_pts_tick"] == 6)
    after = next(f for f in revised["frames"] if f["sample"]["native_pts_tick"] == 6)
    assert before["life"]["value"] == "DEAD"
    assert after["life"]["value"] == "UNKNOWN"
    assert after["life"]["hypotheses"] == ["ALIVE", "DEAD", "DOWNED", "UNKNOWN"]
    assert after["camera"]["value"] == "UNKNOWN"
    assert "SELF" in after["camera"]["hypotheses"]
    assert after["life"]["forward_estimate"] == before["life"]
    assert any(h["sample"] == after["sample"] for h in revised["return_display_tail_projection_history"])
    assert all(h["qualified"] is False for h in revised["return_display_tail_projection_history"])
    assert revised["qualified_facts"] == revised["qualified_events"] == []
    assert revised["frames"][-1]["life"]["value"] == "ALIVE"


@pytest.mark.parametrize("change", [
    {"return_source": "d"},
    {"return_epoch": "other"},
    {"tail_score": [1, 1], "return_score": [2, 1]},
    {"tail_signals": ["spectator"]},
    {"return_tick": 11},
])
def test_return_tail_rejects_discontinuity_conflict_and_distant_return(change):
    revised = replay(return_rows(**change), return_display_tail=True)
    target = next(f for f in revised["frames"] if f["sample"]["native_pts_tick"] == 6)
    assert target["life"]["reason"] != "next_round_self_return_bracket_candidate"


def test_direct_death_is_never_revised_by_return_tail():
    rows = return_rows()
    rows.append(row(6, ["death"]))
    result = replay(rows, return_display_tail=True)
    direct = next(f for f in result["frames"] if f["sample"]["native_pts_tick"] == 6)
    assert direct["life"]["value"] == "DEAD"
    assert result["return_display_tail_projection_history"] == []


def test_buy_clock_tail_preserves_phase_alternatives_and_default():
    rows = [row(0, ["buy"], score=[1, 0], timer=1),
            row(1, score=[1, 0], timer=0),
            row(2, ["active"], score=[1, 0], timer=99)]
    baseline = replay(rows)
    revised = replay(rows, buy_clock_tail=True)
    assert baseline["frames"][1]["round"]["value"] == "BUY"
    phase = revised["frames"][1]["round"]
    assert phase["value"] == "UNKNOWN"
    assert phase["hypotheses"] == ["ACTIVE", "BUY", "UNKNOWN"]
    assert phase["forward_estimate"] == baseline["frames"][1]["round"]
    assert revised["transitions"] == baseline["transitions"]
    assert revised["qualified_facts"] == revised["qualified_events"] == []
    assert len(revised["buy_clock_tail_projection_history"]) == 1


@pytest.mark.parametrize("change", [
    {"timer": 2},
    {"middle_score": [1, 1]},
    {"end_score": [2, 0]},
    {"end_source": "d"},
    {"end_epoch": "other"},
    {"end_tick": 8},
])
def test_buy_clock_tail_rejects_unwitnessed_or_incompatible_brackets(change):
    middle = row(1, score=change.get("middle_score", [1, 0]), timer=change.get("timer", 0))
    end = row(change.get("end_tick", 2), ["active"], score=change.get("end_score", [1, 0]),
              source=change.get("end_source", "a"), epoch=change.get("end_epoch", "e"))
    result = replay([row(0, ["buy"], score=[1, 0], timer=1), middle, end], buy_clock_tail=True)
    assert result["buy_clock_tail_projection_history"] == []


def test_opt_in_flags_require_offline_mode():
    with pytest.raises(ValueError, match="offline"):
        DevelopmentGameTimeline(forward_only=True, return_display_tail=True)
    with pytest.raises(ValueError, match="offline"):
        DevelopmentGameTimeline(forward_only=True, buy_clock_tail=True)
