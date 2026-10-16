"""Synthetic fail-closed controls for experimental report/victim onset timing."""

from dataclasses import replace

import pytest

from valorant_ai_coach.experimental.report_victim_episode import ReportVictimEpisodeProbe
from valorant_ai_coach.experimental.subject_death import SourceBinding


def source(tick: int, *, segment: str = "video-segment") -> SourceBinding:
    return SourceBinding(
        video_sha256="a" * 64,
        pts_ticks=tick, time_base_num=1, time_base_den=60,
        segment_id=segment, pixel_sha256=f"{tick:064x}",
        code_fingerprint="b" * 64, profile_fingerprint="c" * 64,
        dependencies_fingerprint="d" * 64,
    )


def test_two_episodes_preserve_first_onset_not_later_confirmed_frame() -> None:
    probe = ReportVictimEpisodeProbe()
    observations = [
        (99, .02, .02, False, "unknown"),
        (100, .98, .10, False, "unknown"),
        (101, .96, .88, False, "unqualified_candidate"),
        (102, .96, .94, False, "duplicate"),
        (190, .03, .01, False, "duplicate"),
        (300, .98, .88, False, "duplicate"),
        (500, .02, .02, True, "unknown"),
        (501, .97, None, False, "unknown"),
        (502, .98, .81, False, "unqualified_candidate"),
        (510, .98, .90, False, "duplicate"),
    ]
    decisions = []
    for tick, report, victim, start, status in observations:
        result = probe.observe(source(tick), report_score=report,
                               victim_score=victim, qualified_new_round=start)
        assert result.status == status
        assert result.qualified is False and result.formal_events == ()
        if result.status == "unqualified_candidate":
            decisions.append(result)
    assert [(x.onset_time_sec, x.confirmation_time_sec) for x in decisions] == [
        (100 / 60, 101 / 60), (501 / 60, 502 / 60),
    ]


def test_persistent_report_toggle_without_new_round_never_rearms() -> None:
    probe = ReportVictimEpisodeProbe()
    probe.observe(source(0), report_score=.02, victim_score=.02)
    result = probe.observe(source(1), report_score=.95, victim_score=.85)
    assert result.status == "unqualified_candidate"
    for tick, report in [(2, .99), (60, .01), (90, .99), (120, .03), (360, .99)]:
        result = probe.observe(source(tick), report_score=report, victim_score=.99)
        assert result.status == "duplicate"
        assert result.formal_events == ()


def test_header_only_victim_only_stale_and_clipped_onset_do_not_emit() -> None:
    probe = ReportVictimEpisodeProbe()
    for tick, report, victim in [
        (0, .99, .99),  # Clip may start with previous report: no prior absence
        (1, .02, .02),
        (2, .98, .12),
        (3, .98, .99),  # after an observed appearance this is allowed
    ]:
        result = probe.observe(source(tick), report_score=report,
                               victim_score=victim)
        if tick == 3:
            assert result.status == "unqualified_candidate"
        else:
            assert result.status == "unknown"


def test_stale_report_onset_rejected_even_with_later_victim() -> None:
    probe = ReportVictimEpisodeProbe()
    probe.observe(source(0), report_score=.03, victim_score=.02)
    probe.observe(source(1), report_score=.99, victim_score=None)
    assert probe.observe(source(70), report_score=.99,
                         victim_score=.99).status == "unknown"


def test_source_change_blocks_until_qualified_new_round() -> None:
    probe = ReportVictimEpisodeProbe()
    probe.observe(source(9), report_score=.02, victim_score=.02)
    assert probe.observe(source(10), report_score=.99,
                         victim_score=.99).status == "unqualified_candidate"
    assert probe.observe(source(11, segment="source-cut"), report_score=.99,
                         victim_score=.99).status == "unknown"
    assert probe.observe(source(12, segment="source-cut"), report_score=.99,
                         victim_score=.99).status == "unknown"
    assert probe.observe(source(13, segment="source-cut"), report_score=.02,
                         victim_score=.02, qualified_new_round=True).status == "unknown"
    assert probe.observe(source(14, segment="source-cut"), report_score=.99,
                         victim_score=.99).status == "unqualified_candidate"
    repeated = replace(source(15, segment="source-cut"),
                       pixel_sha256=source(14, segment="source-cut").pixel_sha256)
    assert probe.observe(repeated, report_score=.99,
                         victim_score=.99).status == "unknown"


def test_report_and_victim_thresholds_are_diagnostic_not_qualifying() -> None:
    probe = ReportVictimEpisodeProbe()
    probe.observe(source(0), report_score=.10, victim_score=.10)
    result = probe.observe(source(1), report_score=.90, victim_score=.80)
    assert result.status == "unqualified_candidate"
    assert result.qualified is False and result.formal_events == ()


@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), 2, -2, "0.95"])
def test_invalid_similarity_values_rejected(value) -> None:
    probe = ReportVictimEpisodeProbe()
    with pytest.raises(ValueError, match="measured image-similarity"):
        probe.observe(source(100), report_score=value,
                      victim_score=.98)  # type: ignore[arg-type]


def test_non_boolean_lifecycle_signal_rejected() -> None:
    probe = ReportVictimEpisodeProbe()
    with pytest.raises(ValueError, match="typed lifecycle"):
        probe.observe(source(10), report_score=.98, victim_score=.98,
                      qualified_new_round=1)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [0, -1, 1.01, float("nan"), float("inf"), True, "0.9"])
def test_invalid_score_floor_rejected(bad) -> None:
    with pytest.raises(ValueError, match="comparison floor"):
        ReportVictimEpisodeProbe(victim_floor=bad)  # type: ignore[arg-type]
