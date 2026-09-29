from __future__ import annotations

from valorant_ai_coach.video.sampling import HudFrameSampler, SampleRequest


def test_pass_a_uses_general_and_change_sensitive_cadences() -> None:
    requests = HudFrameSampler().pass_a(1.0)
    assert [item.time_sec for item in requests] == [0.0, 0.25, 0.5, 0.75, 1.0]
    at_half = next(item for item in requests if item.time_sec == 0.5)
    assert set(at_half.purposes) == {"general_hud", "change_sensitive_hud"}


def test_pass_b_is_dense_bounded_and_merge_deduplicates() -> None:
    sampler = HudFrameSampler(burst_fps=10, burst_radius_sec=0.2)
    dense = sampler.pass_b(2.0, [1.0, 1.0, 99.0])
    assert dense[0].time_sec == 0.8
    assert dense[-1].time_sec == 1.2
    merged = sampler.merge(
        [SampleRequest(1.0, ("general_hud",))],
        [SampleRequest(1.0, ("hud_change_burst",))],
    )
    assert merged == (
        SampleRequest(1.0, ("general_hud", "hud_change_burst")),
    )


def test_change_times_tracks_hud_changes_only() -> None:
    values = lambda hp: {  # noqa: E731
        "primary_state": "live_first_person",
        "state_flags": [],
        "values": {"hp": hp, "kill_feed_rows": []},
    }
    observations = [
        {"time_sec": 0.0, **values(100)},
        {"time_sec": 0.5, **values(100)},
        {"time_sec": 1.0, **values(75)},
    ]
    assert HudFrameSampler.change_times(observations) == (1.0,)
