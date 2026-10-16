"""Controls for visual co-occurrence candidates; no formal event authority."""

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


def test_two_death_episodes_only_with_independently_qualified_rearm() -> None:
    probe = ReportVictimEpisodeProbe()
    rows = [
        (source(100), .99, .12, False, "unknown"),
        (source(101), .97, .83, False, "unqualified_candidate"),
        (source(102), .95, .94, False, "duplicate"),
        (source(130), .97, None, False, "duplicate"),
        (source(300), .99, .88, False, "duplicate"),
        (source(500), .02, .12, True, "unknown"),
        (source(501), .97, None, False, "unknown"),
        (source(502), .98, .81, False, "unqualified_candidate"),
        (source(510), .98, .90, False, "duplicate"),
    ]
    for frame, report, victim, start, status in rows:
        result = probe.observe(frame, report_score=report, victim_score=victim,
                               qualified_new_round=start)
        assert result.status == status
        assert result.qualified is False and result.formal_events == ()


def test_persistent_report_after_disappearance_never_rearms_itself() -> None:
    probe = ReportVictimEpisodeProbe()
    assert probe.observe(source(0), report_score=.95,
                         victim_score=.85).status == "unqualified_candidate"
    for tick in (1, 60, 90, 120, 360):
        # Report toggle and persistent scoreboard/panel cause no new Death.
        result = probe.observe(source(tick), report_score=.99,
                               victim_score=.99)
        assert result.status == "duplicate"
        assert result.formal_events == ()


def test_report_only_killfeed_only_and_missing_data_are_unknown() -> None:
    probe = ReportVictimEpisodeProbe()
    for tick, a, b in [
        (0, .99, None), (1, .98, .12), (2, None, .99),
        (3, .89, .99), (4, .99, .79), (5, -1, .99),
    ]:
        result = probe.observe(source(tick), report_score=a, victim_score=b)
        assert result.status == "unknown"
    assert probe.observe(source(6), report_score=.90,
                         victim_score=.80).status == "unqualified_candidate"


def test_source_break_and_repeated_raster_do_not_auto_rearm() -> None:
    probe = ReportVictimEpisodeProbe()
    assert probe.observe(source(10), report_score=.99,
                         victim_score=.99).status == "unqualified_candidate"
    broken = source(11, segment="source-cut")
    result = probe.observe(broken, report_score=.99, victim_score=.99)
    assert result.status == "unknown"
    result = probe.observe(source(12, segment="source-cut"),
                           report_score=.99, victim_score=.99)
    assert result.status == "unknown"
    assert probe.observe(source(13, segment="source-cut"), report_score=.99,
                         victim_score=.99, qualified_new_round=True
                         ).status == "unqualified_candidate"
    repeated = replace(source(14, segment="source-cut"),
                       pixel_sha256=source(13, segment="source-cut").pixel_sha256)
    assert probe.observe(repeated, report_score=.99,
                         victim_score=.99).status == "unknown"


@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), 2, -2, "0.95"])
def test_invalid_similarity_values_rejected(value) -> None:
    probe = ReportVictimEpisodeProbe()
    with pytest.raises(ValueError, match="measured image-similarity"):
        probe.observe(source(100), report_score=value, victim_score=.98)  # type: ignore[arg-type]


def test_wrong_lifecycle_signal_rejected() -> None:
    probe = ReportVictimEpisodeProbe()
    with pytest.raises(ValueError, match="typed lifecycle"):
        probe.observe(source(10), report_score=.98, victim_score=.98,
                      qualified_new_round=1)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [0, 1.01, float("nan"), float("inf"), True, .90])
def test_invalid_score_floor_rejected(bad) -> None:
    if type(bad) is float and bad == .90:
        ReportVictimEpisodeProbe(report_floor=bad)
        return
    with pytest.raises(ValueError, match="comparison floor"):
        ReportVictimEpisodeProbe(victim_floor=bad)  # type: ignore[arg-type]
