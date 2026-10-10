from __future__ import annotations

from pathlib import Path

import pytest

from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.rounds import RoundPackageBuilder, aggregate_observation_quality
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata

ROOT = Path(__file__).resolve().parents[2]


def observation(
    time_sec: float,
    *,
    hud_confidence: float = 0.9,
    ally_alive: int = 5,
    enemy_alive: int = 5,
    spike_state: str = "unknown",
) -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "time_sec": time_sec,
        "frame_index": round(time_sec * 60),
        "primary_state": "live_first_person",
        "state_flags": [],
        "view_context": {
            "remote_view_type": "none",
            "is_player_world_view_trustworthy": True,
        },
        "values": {
            "round_time_remaining_sec": max(0, 100 - time_sec),
            "score_ally": 1,
            "score_enemy": 2,
            "ally_alive": ally_alive,
            "enemy_alive": enemy_alive,
            "hp": 100,
            "armor": 50,
            "ammo_current": 25,
            "ammo_reserve": 50,
            "weapon_text": None,
            "spike_state": spike_state,
            "location_text": None,
            "kill_feed_rows": [],
            "ability_slots": [],
            "combat_report_visible": False,
            "buy_phase_visible": False,
            "round_end_text": None,
            "zone_id": None,
            "player_specific_hud_valid": True,
        },
        "quality": {
            "hud_confidence": hud_confidence,
            "visual_confidence": 0.0,
            "occluded_rois": [],
            "notes": [],
            "state_confidence": hud_confidence,
            "roi_confidence": {},
        },
    }


def event(event_id: str, time_sec: float, event_type: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "time_sec": time_sec,
        "type": event_type,
        "actor": "system",
        "attributes": {},
        "confidence": 0.9,
    }


def test_hud_observation_schema_and_cross_field_contract() -> None:
    validator = SchemaValidator()
    validator.validate_hud_observation(observation(1.0))
    invalid = observation(1.0)
    invalid["primary_state"] = "spectator_first_person"
    invalid["view_context"]["is_player_world_view_trustworthy"] = True  # type: ignore[index]
    with pytest.raises(ValueError, match="world view"):
        validator.validate_hud_observation(invalid)


def test_quality_formula_matches_patch_logic_case() -> None:
    samples = [
        observation(2 / 3, hud_confidence=0.95),
        observation(2.0, hud_confidence=0.9),
        observation(10 / 3, hud_confidence=0.8),
    ]
    quality = aggregate_observation_quality(
        samples, 0.0, 5.0, coverage_radius_sec=2 / 3
    )
    assert quality["timeline_completeness"] == pytest.approx(0.8, abs=0.001)
    assert quality["hud_confidence"] == pytest.approx(0.72, abs=0.001)
    assert quality["missing_intervals"] == pytest.approx(
        [{"start_sec": 4.0, "end_sec": 5.0}], abs=0.001
    )


def test_builder_produces_schema_valid_round_package_without_visual_fabrication(
    tmp_path: Path,
) -> None:
    validator = SchemaValidator()
    contract = EventSourceContract.load(ROOT / "config" / "event_source_contract_v1.json")
    builder = RoundPackageBuilder(contract=contract, validator=validator)
    metadata = VideoMetadata(
        path=tmp_path / "match.mp4",
        duration_sec=5.0,
        width=1920,
        height=1080,
        fps=60,
        video_codec="h264",
        audio_codec=None,
        has_audio=False,
        file_size=0,
    )
    observations = [
        observation(1.0),
        observation(2.0, enemy_alive=4),
        observation(3.0, enemy_alive=4, spike_state="planted"),
    ]
    packages = builder.build(
        match_id="M-HUD",
        video_metadata=metadata,
        hud_observations=observations,
        hud_events=[event("H-START", 1.0, "round_start"), event("H-END", 3.0, "round_end")],
    )
    assert len(packages) == 1
    package = packages[0]
    validator.validate_round_package(package)
    assert package["round_meta"]["round_result"] == "unknown"
    assert package["state_snapshots"]
    assert {item["type"] for item in package["events"]}.isdisjoint(
        {"shot", "peek", "movement_state", "utility_used"}
    )
    assert "objective_state" in {item["type"] for item in package["events"]}


def practical_candidate(kind: str, timestamp: float, confirmation: float | None = None):
    from valorant_ai_coach.rounds.boundaries import BoundaryObservation

    return BoundaryObservation(
        kind, "provisional", timestamp, confirmation,
        (timestamp,) if confirmation is None else (timestamp, confirmation),
        0.9, {"scope": "global_system", "test_evidence": "synthetic composite"},
    )


@pytest.fixture
def practical_build(tmp_path: Path):
    contract = EventSourceContract.load(ROOT / "config" / "event_source_contract_v1.json")
    builder = RoundPackageBuilder(contract=contract, validator=SchemaValidator())
    metadata = VideoMetadata(tmp_path / "match.mp4", 8.0, 1920, 1080, 60, "h264", None, False, 0)

    def build(**kwargs):
        return builder.build(
            match_id="PRACTICAL", video_metadata=metadata,
            hud_observations=[observation(n / 2) for n in range(1, 17)],
            hud_events=kwargs.pop("hud_events", []), **kwargs,
        )
    return build


def test_practical_partition_keeps_candidates_out_of_formal_events(practical_build) -> None:
    packages = practical_build(boundary_mode="practical", provisional_boundaries=[
        practical_candidate("round_start", 1.0, 1.5),
        practical_candidate("round_end", 3.0, 4.0),
        practical_candidate("round_start", 5.0, 5.5),
    ])
    starts = [p for p in packages if p["round_lifecycle"]["start"]["status"] == "provisional"]
    assert len(starts) == 2
    assert starts[0]["round_lifecycle"]["start"]["candidate"]["boundary_time_sec"] == 1.0
    assert starts[0]["round_lifecycle"]["start"]["candidate"]["confirmation_time_sec"] == 1.5
    assert starts[1]["round_lifecycle"]["end"]["status"] == "unknown"
    for package in packages:
        assert package["round_lifecycle"]["observed_round_no"] is None
        assert package["observation_quality"]["timeline_completeness"] == 0
        assert not any(e["type"] in {"round_start", "round_end"} for e in package["events"])
    for left, right in zip(packages, packages[1:], strict=False):
        assert left["round_window"]["end_sec"] <= right["round_window"]["start_sec"]
    times = [s["time_sec"] for p in packages for s in p["state_snapshots"]]
    assert len(times) == len(set(times))


def test_strict_rejects_provisional_opt_in_and_keeps_legacy_schema(practical_build) -> None:
    with pytest.raises(ValueError, match="opt-in"):
        practical_build(provisional_boundaries=[practical_candidate("round_start", 1.0)])
    packages = practical_build(hud_events=[event("S", 1.0, "round_start"),
                                         event("E", 3.0, "round_end")])
    assert all("round_lifecycle" not in p for p in packages)


def test_practical_cannot_self_attest_confirmed_or_cross_source_cut(practical_build) -> None:
    from dataclasses import replace

    candidate = practical_candidate("round_start", 1.0, 2.0)
    with pytest.raises(ValueError, match="formal HUD"):
        practical_build(boundary_mode="practical",
                        provisional_boundaries=[replace(candidate, boundary_status="confirmed")])
    with pytest.raises(ValueError, match="discontinuity"):
        practical_build(boundary_mode="practical", provisional_boundaries=[candidate],
                        continuity_breaks=[1.5])


def test_practical_duplicate_is_suppressed_and_competing_starts_withheld(practical_build) -> None:
    candidate = practical_candidate("round_start", 1.0)
    packages = practical_build(
        boundary_mode="practical", provisional_boundaries=[candidate, candidate]
    )
    assert sum(p["round_lifecycle"]["start"]["status"] == "provisional" for p in packages) == 1
    packages = practical_build(boundary_mode="practical", provisional_boundaries=[
        candidate, practical_candidate("round_start", 2.0),
    ])
    assert all(p["round_lifecycle"]["start"]["status"] == "unknown" for p in packages)


def test_practical_formal_boundary_has_priority_and_is_schema_bound(practical_build) -> None:
    packages = practical_build(boundary_mode="practical", provisional_boundaries=[
        practical_candidate("round_start", 1.0)],
        hud_events=[event("S", 1.0, "round_start"), event("E", 3.0, "round_end")])
    package = next(p for p in packages
                   if p["round_lifecycle"]["start"]["status"] == "confirmed")
    assert package["round_lifecycle"]["start"]["status"] == "confirmed"
    assert package["round_lifecycle"]["start"]["candidate"] is None
    package["round_lifecycle"]["start"]["formal_event_id"] = "NOT-PRESENT"
    with pytest.raises(ValueError, match="formal event"):
        SchemaValidator().validate_round_package(package)


def test_practical_package_sqlite_roundtrip(practical_build, tmp_path: Path) -> None:
    from valorant_ai_coach.storage.repository import SQLiteRepository

    package = practical_build(boundary_mode="practical", provisional_boundaries=[
        practical_candidate("round_start", 1.0, 2.0)])[0]
    repository = SQLiteRepository(tmp_path / "practical.sqlite")
    repository.save_round_package(package)
    restored = repository.get_round_package(package["match_id"], package["round_no"])
    assert restored == package
    SchemaValidator().validate_round_package(restored)


def test_uncertain_practical_package_preserves_facts_without_scoring(practical_build) -> None:
    from unittest.mock import Mock

    from valorant_ai_coach.application.round_analyzer import RoundAnalyzer

    package = practical_build(boundary_mode="practical", provisional_boundaries=[
        practical_candidate("round_start", 1.0)])[0]
    fact_builder = Mock()
    fact_builder.enrich.side_effect = lambda item: item
    selector, engine, coach = Mock(), Mock(), Mock()
    analyzer = RoundAnalyzer(fact_builder=fact_builder, selector=selector, rule_engine=engine,
                             coach=coach, validator=SchemaValidator())
    analysis = analyzer.analyze(package)
    assert analysis.round_package == package
    assert analysis.output["evaluations"] == []
    selector.select.assert_not_called()
    engine.evaluate.assert_not_called()
    coach.evaluate.assert_not_called()


@pytest.mark.parametrize("candidates", [[], [practical_candidate("round_end", 3.0)]])
def test_practical_missing_start_stays_unknown(practical_build, candidates) -> None:
    packages = practical_build(boundary_mode="practical", provisional_boundaries=candidates)
    assert packages
    assert all(p["round_lifecycle"]["start"]["status"] == "unknown" for p in packages)
    assert all(p["observation_quality"]["timeline_completeness"] == 0 for p in packages)


def test_practical_simultaneous_opposite_candidates_are_not_a_round(practical_build) -> None:
    packages = practical_build(boundary_mode="practical", provisional_boundaries=[
        practical_candidate("round_start", 1.0), practical_candidate("round_end", 1.0)])
    assert all(p["round_lifecycle"][name]["status"] == "unknown"
               for p in packages for name in ("start", "end"))


def test_practical_separate_source_segments_never_pair_boundaries(practical_build) -> None:
    packages = practical_build(boundary_mode="practical", continuity_breaks=[2.0],
                              provisional_boundaries=[
                                  practical_candidate("round_start", 1.0),
                                  practical_candidate("round_end", 3.0)])
    assert all(not (p["round_window"]["start_sec"] < 2.0 < p["round_window"]["end_sec"])
               for p in packages)
    assert all(not (p["round_lifecycle"]["start"]["status"] == "provisional"
                    and p["round_lifecycle"]["end"]["status"] == "provisional") for p in packages)


def test_practical_consumer_pipeline_resume_preserves_uncertainty_without_scoring(
    practical_build, tmp_path: Path,
) -> None:
    from threading import Event

    from tests.integration.test_mock_e2e import build_pipeline
    from valorant_ai_coach.application import AnalysisCancelled

    source = tmp_path / 'match.mp4'
    source.write_bytes(b'video')
    packages = practical_build(boundary_mode='practical', provisional_boundaries=[
        practical_candidate('round_start', 1., 1.5),
        practical_candidate('round_end', 3., 4.),
        practical_candidate('round_start', 5., 5.5),
    ])
    # Consumer integration uses already produced synthetic Packages; no pixel or
    # qualification claim. Native source collection has separate integration tests.
    pipeline, repository, video, clips = build_pipeline(tmp_path, source, list(packages))
    cancel = Event()
    retained_number = next(p['round_no'] for p in packages
                           if p['round_lifecycle']['start']['status'] == 'provisional')

    def cancel_after_first(_progress, message):
        if message == f'区間 {retained_number} の観測を保存しました（境界未確定・採点保留）':
            cancel.set()

    with pytest.raises(AnalysisCancelled):
        pipeline.analyze_video(source, match_id='P-RESUME', cancel_event=cancel,
                               progress_cb=cancel_after_first)
    stored = repository.get_round_package('P-RESUME', retained_number)
    assert stored['round_lifecycle'] == packages[retained_number - 1]['round_lifecycle']
    assert stored['frames'] == []
    first_facts = stored['deterministic_facts']
    restored = pipeline.resume_analysis('P-RESUME')
    assert restored.status == 'completed'
    stored = repository.get_round_package('P-RESUME', retained_number)
    assert stored['deterministic_facts'] == first_facts
    assert stored['round_lifecycle'] == packages[retained_number - 1]['round_lifecycle']
    assert repository.get_match_result('P-RESUME')['evaluations'] == []
    assert video.requested_timestamps == [] and clips.calls == 0
    assert restored.rounds[retained_number - 1].output['analysis_id'] == (
        f'RESTORED-P-RESUME-R{retained_number}'
    )
