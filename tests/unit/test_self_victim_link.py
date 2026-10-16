"""Fail-closed synthetic controls for experimental scoreboard/victim name linking."""

from dataclasses import replace

import pytest

from valorant_ai_coach.experimental.self_victim_link import link_source_player_to_victim
from valorant_ai_coach.experimental.subject_death import (
    ReviewStatus,
    SourceBinding,
    SubjectObservation,
    SubjectRelation,
    SubjectRole,
)


def source(frame: int, *, segment: str = "clip-episode") -> SourceBinding:
    return SourceBinding(
        video_sha256="a" * 64, pts_ticks=frame, time_base_num=1, time_base_den=60,
        segment_id=segment, pixel_sha256=f"{frame:064x}",
        code_fingerprint="b" * 64, profile_fingerprint="c" * 64,
        dependencies_fingerprint="d" * 64,
    )


def owner_and_victim() -> tuple[SubjectObservation, SubjectObservation]:
    owner = SubjectObservation(
        "owner", source(100), SubjectRole.SOURCE_PLAYER_BINDING,
        SubjectRelation.UNKNOWN, "e" * 64, .97,
        "scoreboard_border_and_name_candidate", (10, 250, 400, 310),
    )
    victim = SubjectObservation(
        "victim", source(110), SubjectRole.VICTIM, SubjectRelation.UNKNOWN,
        "e" * 64, .95, "killfeed_victim_text", (1100, 20, 1700, 90),
    )
    return owner, victim


def test_agreeing_native_names_are_unqualified_not_formal_death() -> None:
    owner, victim = owner_and_victim()
    result = link_source_player_to_victim(owner, victim)
    assert result.status == "unqualified_self_victim_candidate"
    assert result.confidence == pytest.approx(.95)
    assert result.qualified is False and result.formal_events == ()
    assert "independent_review_missing" in result.blockers
    assert "death_transition_corroboration_missing" in result.blockers
    assert owner.relation == victim.relation == SubjectRelation.UNKNOWN


def test_source_review_does_not_promote_to_qualification() -> None:
    owner, victim = owner_and_victim()
    reviewed = (
        replace(owner, review_status=ReviewStatus.SOURCE_REVIEWED,
                review_sha256="f" * 64),
        replace(victim, review_status=ReviewStatus.SOURCE_REVIEWED,
                review_sha256="f" * 64),
    )
    result = link_source_player_to_victim(*reviewed)
    assert result.status == "unqualified_self_victim_candidate"
    assert "independent_review_missing" not in result.blockers
    assert result.qualified is False and result.formal_events == ()


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("killer", "not_victim_role"),
        ("wrong_name", "victim_is_not_recording_player"),
        ("foreign_segment", "source_context_mismatch"),
        ("stale", "stale_or_ambiguous_source_time"),
        ("same_frame_pixels", "no_independent_source_frames"),
        ("same_native_pts", "no_independent_source_frames"),
        ("wrong_role_source", "unqualified_role_method"),
        ("overlap", "overlapping_evidence_rois"),
        ("weak_confidence", "text_or_marker_support_insufficient"),
        ("wrong_reader", "unqualified_role_method"),
        ("missing_token", "name_evidence_missing"),
    ],
)
def test_never_joins_ambiguous_or_unowned_evidence(mutation, reason) -> None:
    owner, victim = owner_and_victim()
    changes = {
        "killer": {"role": SubjectRole.KILLER},
        "wrong_name": {"subject_token": "9" * 64},
        "foreign_segment": {"source": source(110, segment="foreign")},
        "stale": {"source": source(170)},
        "same_frame_pixels": {
            "source": replace(victim.source, pixel_sha256=owner.source.pixel_sha256)
        },
        "same_native_pts": {"source": replace(victim.source, pts_ticks=100)},
        "wrong_role_source": {"method": "combat_report_victim_text"},
        "overlap": {"roi": owner.roi},
        "weak_confidence": {"confidence": .89},
        "wrong_reader": {"method": "combat_report_killer_text"},
        "missing_token": {"subject_token": None},
    }
    result = link_source_player_to_victim(owner, replace(victim, **changes[mutation]))
    assert result.status == "unknown" and reason in result.blockers
    assert result.qualified is False and result.formal_events == ()


def test_absent_evidence_and_invalid_horizon_fail_closed() -> None:
    owner, victim = owner_and_victim()
    assert link_source_player_to_victim(None, victim).status == "unknown"
    assert link_source_player_to_victim(owner, None).status == "unknown"
    for invalid in (0, -1, 1.001, float("nan"), float("inf"), True):
        with pytest.raises(ValueError, match="horizon"):
            link_source_player_to_victim(owner, victim, max_age_sec=invalid)


def test_same_source_but_changed_code_or_profile_never_joins() -> None:
    owner, victim = owner_and_victim()
    for change in (
        {"code_fingerprint": "9" * 64},
        {"profile_fingerprint": "9" * 64},
        {"dependencies_fingerprint": "9" * 64},
        {"video_sha256": "9" * 64},
    ):
        altered = replace(victim, source=replace(victim.source, **change))
        result = link_source_player_to_victim(owner, altered)
        assert result.status == "unknown"
        assert "source_context_mismatch" in result.blockers


def test_1_second_exact_horizon_is_allowed_but_not_qualifying() -> None:
    owner, victim = owner_and_victim()
    victim = replace(victim, source=source(160))
    result = link_source_player_to_victim(owner, victim)
    assert result.status == "unqualified_self_victim_candidate"
    assert result.formal_events == ()
