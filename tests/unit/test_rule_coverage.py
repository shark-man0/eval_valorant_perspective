from __future__ import annotations

import cv2
import numpy as np

from valorant_ai_coach.knowledge.timeline_view import TimelineView
from valorant_ai_coach.knowledge.top_bar import BAR_ORIGIN, CENTRE_BOX, spike_planted_indicator
from valorant_ai_coach.rules.coverage import (
    LEVELS,
    blocker_ranking,
    coverage,
    load_producer_status,
    load_rules,
    summarize,
)
from valorant_ai_coach.rules.development_readiness import (
    FeedKill,
    Observation,
    derive,
    rule_occurrences,
)
from valorant_ai_coach.rules.recorder_life import Round, reconcile, rounds_from_alive_counts


def test_status_registry_covers_every_rule_input() -> None:
    status = load_producer_status()
    rules = load_rules()
    assert len(rules) == 44
    for rule in rules:
        for event in rule["trigger"]["trigger_event_types"]:
            assert event in status["events"], event
        for predicate in rule["trigger"]["required_state_predicates"]:
            assert predicate["fact_key"] in status["facts"], predicate["fact_key"]
    for group in ("events", "facts"):
        for item in status[group].values():
            assert LEVELS.index(item["after"]) >= LEVELS.index(item["before"])


def test_readiness_before_and_after() -> None:
    before = summarize(coverage("before"))
    after = summarize(coverage("after"))
    assert sum(before.values()) == sum(after.values()) == 44
    assert before["qualified"] == after["qualified"] == 0
    assert after["development"] > before["development"]
    ready = {r.rule_id for r in coverage("after") if r.readiness == "development"}
    assert {"UTL-01", "ADV-08", "ROLE-02", "INFO-03", "ADV-01", "ADV-02", "OBJ-03",
            "POS-04", "DEC-05"} <= ready
    assert all(not blocker.startswith("fact:player_role")
               for blocker, _ in blocker_ranking(coverage("after")))


def _obs(sec: float, agent: str | None, charges: tuple[float, float, float, float],
         ally: int, enemy: int, *, spike: bool | None = None,
         feed: tuple[FeedKill, ...] | None = None) -> Observation:
    return Observation(sec, agent is not None, agent, 0.9 if agent else 0.0, charges, ally, enemy,
                       spike, feed)


def test_derived_candidates_and_rule_occurrences() -> None:
    own_death = FeedKill("enemy", "ally", "Omen", False, True)
    series = [
        _obs(0, "Omen", (1, 1, 1, 0), 5, 5, spike=False, feed=()),
        _obs(5, "Omen", (1, 0, 1, 1), 5, 4, spike=False,
             feed=(FeedKill("ally", "enemy", "Jett", True, False),)),  # recorder's kill
        _obs(10, "Omen", (1, 0, 1, 1), 1, 3, spike=True, feed=()),  # plant; last ally alive
        _obs(15, "Sova", (1, 1, 1, 0), 1, 3, spike=True, feed=(own_death,)),
        _obs(20, "Sova", (1, 1, 1, 0), 1, 3, spike=True, feed=(own_death,)),  # same entry
        _obs(25, "Omen", (1, 1, 1, 1), 5, 5, spike=False, feed=()),  # next round
    ]
    derivation = derive(series, "Omen", "controller")
    samples = derivation.samples
    assert derivation.sources["rounds"] == "provisional_top_bar_reset"
    assert "utility_used" in samples[1].events and "kill" in samples[1].events
    assert samples[1].facts["first_kill_by_player"] is True
    assert samples[1].facts["first_death_by_player"] is False
    assert samples[1].facts["ultimate_available"] is True
    assert samples[2].facts["clutch_state"] is True
    assert {"spike_planted", "objective_state"} <= samples[2].events
    assert samples[3].facts["player_died"] is True and "player_death" in samples[3].events
    assert samples[3].facts["utility_available_count"] == 2
    assert "kill" not in samples[4].events  # a persisting entry is not a new kill
    assert len(derivation.reconciliation.deaths) == 1
    counts = rule_occurrences(load_rules(), samples)
    assert counts["UTL-01"] == 1
    assert counts["ROLE-02"] == 1
    assert counts["ADV-02"] == 1 and counts["ADV-01"] == 0
    assert counts["OBJ-03"] == 1
    assert counts["ROLE-03"] == 0  # initiator rule never fires for a controller


def test_round_reconciliation_dedupes_revives_and_bounds() -> None:
    rounds = rounds_from_alive_counts([(0, 5, 5), (10, 3, 4), (40, 5, 5), (60, 2, 2)])
    assert [(r.start, r.end) for r in rounds] == [(0, 40), (40, None)]
    result = reconcile(rounds, {"timeline": [12.0, 50.0], "kill_feed": [14.0, 30.0, -5.0]},
                       live_samples=[21.0, 27.0, 45.0])
    deaths = [(d.round_index, d.sec, sorted(d.sources), d.after_revive) for d in result.deaths]
    # 12 + 14 merge; 30 is a second death after the recorder was live again 21-27 s (revive).
    assert deaths == [(0, 12.0, ["kill_feed", "timeline"], False), (0, 30.0, ["kill_feed"], True),
                      (1, 50.0, ["timeline"], False)]
    assert result.dropped["outside_round"] == 1
    no_revive = reconcile([Round(0, 40)], {"hud": [12.0, 30.0]})
    assert len(no_revive.deaths) == 1 and no_revive.dropped["duplicate"] == 1
    spectating = reconcile([Round(0, 40)], {"hud": [30.0]}, spectating_at=lambda t: t > 20)
    assert not spectating.deaths and spectating.dropped["while_spectating"] == 1


def test_timeline_drives_self_view_and_rounds() -> None:
    timeline = TimelineView.from_compact({
        "states": [[0.0, "BUY", "ALIVE", "SELF", 1, "OBSERVED"],
                   [10.0, "ACTIVE", "DEAD", "SPECTATOR", 1, "OBSERVED"],
                   [30.0, "BUY", "ALIVE", "SELF", 2, "OBSERVED"]],
        "events": [["round_start", 0.0, 0.2], ["death_hypothesis", 9.8, 10.0],
                   ["round_end", 25.0, 25.2], ["round_start", 30.0, 30.2]]})
    series = [_obs(0, "Omen", (1, 1, 1, 0), 5, 5), _obs(5, "Omen", (1, 1, 1, 0), 5, 5),
              _obs(10, "Omen", (1, 1, 1, 0), 4, 5),  # HUD still looks like Omen
              _obs(15, "Sova", (1, 1, 1, 0), 4, 5), _obs(30, "Omen", (1, 1, 1, 0), 5, 5)]
    derivation = derive(series, "Omen", "controller", timeline)
    assert {k: derivation.sources[k] for k in ("rounds", "self_view", "deaths", "side")} == {
        "rounds": "timeline", "self_view": "timeline", "deaths": "kill_feed+timeline",
        "side": "unobserved"}
    assert "ability_state" not in derivation.samples[2].events  # timeline says spectating
    assert [s.sec for s in derivation.samples if "player_death" in s.events] == [10.0]


def test_spike_indicator_reads_red_icon() -> None:
    crop = np.full((100, 1155, 3), 90, np.uint8)
    assert spike_planted_indicator(crop)[0] is False
    x0, y0, x1, y1 = CENTRE_BOX
    cv2.circle(crop, ((x0 + x1) // 2 - BAR_ORIGIN[0], (y0 + y1) // 2), 20, (0, 0, 230), -1)
    planted, fraction = spike_planted_indicator(crop)
    assert planted and fraction > 0.06


def test_side_from_spike_carrier_and_half_structure() -> None:
    from valorant_ai_coach.rules.side import RoundOrdinal, infer_sides

    resolved = infer_sides([3, 7], rounds_per_half=12)
    assert resolved.status == "half_structure" and resolved.first_half_side == "attack"
    assert resolved.side(0) == ("attack", "half_structure")
    assert resolved.side(3) == ("attack", "spike_carried")
    assert resolved.side(12) == ("defense", "half_structure")
    assert resolved.side(24) is None  # overtime side order is not in the knowledge base
    second = infer_sides([15], rounds_per_half=12)
    assert second.first_half_side == "defense" and second.side(0) == ("defense", "half_structure")
    conflict = infer_sides([2, 14], rounds_per_half=12)
    assert conflict.status == "conflict" and conflict.side(5) is None
    assert conflict.side(14) == ("attack", "spike_carried")
    assert infer_sides([], rounds_per_half=12).status == "unobserved"
    ordinal = RoundOrdinal([(0, 3), (50, 3), (100, 4)], [(0, 5), (50, 5), (100, 5)])
    assert ordinal.at(25) == 8 and ordinal.at(100) == 9
    assert ordinal.at(-1) is None and ordinal.at(500) is None  # stale read


def test_score_track_keeps_confirmed_monotonic_reads() -> None:
    from valorant_ai_coach.knowledge.score_reader import score_track

    reads = [(0, 1), (5, 1), (10, 7), (15, 1), (20, 2), (25, 2), (30, None), (35, 8), (40, 8),
             (45, 3), (50, 3)]
    assert score_track(reads) == [(0, 1), (5, 1), (20, 2), (25, 2), (45, 3), (50, 3)]


def test_spike_carrier_reader_matches_template() -> None:
    from valorant_ai_coach.knowledge.spike_carrier import SEARCH_WINDOW, SpikeCarrierReader

    rng = np.random.default_rng(3)
    template = np.zeros((26, 40), np.uint8)
    cv2.circle(template, (18, 12), 9, 255, 2)
    cv2.line(template, (36, 0), (36, 25), 230, 1)
    reader = SpikeCarrierReader(template)
    crop = rng.integers(60, 90, (208, 124, 3)).astype(np.uint8)
    blank = reader.read(crop)
    assert not blank.carried
    x, y = SEARCH_WINDOW[0] + 24, SEARCH_WINDOW[1] + 1
    crop[y:y + 26, x:x + 40] = np.maximum(crop[y:y + 26, x:x + 40], template[..., None])
    hit = reader.read(crop)
    assert hit.carried and hit.position == (x, y)


def test_side_facts_and_round_start_events() -> None:
    def obs(sec: float, ally: int, enemy: int, carried: bool, score: tuple[int, int]
            ) -> Observation:
        return Observation(sec, True, "Omen", 0.9, (1, 1, 1, 0), ally, enemy,
                           spike_carried=carried, spike_score=1.0 if carried else 0.1,
                           score=score)

    series = [obs(0, 5, 5, True, (0, 0)), obs(50, 4, 5, False, (0, 0)),  # recorder carries
              obs(100, 5, 5, False, (1, 0)), obs(150, 5, 4, False, (1, 0)),
              obs(200, 5, 5, False, (1, 1)), obs(250, 5, 4, False, (1, 1))]
    derivation = derive(series, "Omen", "controller", rounds_per_half=1)
    samples = derivation.samples
    assert derivation.sources["side"] == "half_structure"
    assert derivation.sources["rounds"] == "provisional_score"
    assert "round_start" in samples[0].events and "round_start" in samples[2].events
    assert "round_start" not in samples[1].events
    assert samples[0].facts["side"] == "attack" and samples[0].facts["spike_carried_by_player"]
    assert samples[3].facts["side"] == "defense"
    assert samples[3].facts["spike_carried_by_player"] is False
    assert "side" not in samples[5].facts  # overtime ordinal, not observed
    assert "spike_carried_by_player" not in samples[1].facts  # attack, not seen carrying


def test_score_reader_reads_two_digit_score() -> None:
    from valorant_ai_coach.knowledge.score_reader import (
        GLYPH_SIZE,
        SCORE_WINDOWS,
        ScoreReader,
        glyph_boxes,
        normalise_glyph,
    )

    def draw(text: str) -> np.ndarray:
        window = np.full((20, 40, 3), 60, np.uint8)
        cv2.putText(window, text, (8, 16), cv2.FONT_HERSHEY_PLAIN, 1.0, (255, 255, 255), 1)
        return window

    templates = np.zeros((10, GLYPH_SIZE[1], GLYPH_SIZE[0]), np.float32)
    for digit in range(10):
        gray, boxes = glyph_boxes(draw(str(digit)))
        assert len(boxes) == 1, digit
        templates[digit] = normalise_glyph(gray, boxes[0])
    reader = ScoreReader(templates)
    bar = np.full((50, 578, 3), 60, np.uint8)
    x0, y0, x1, y1 = SCORE_WINDOWS["ally"]
    bar[y0:y1, x0:x1] = draw("12")
    reading = reader.read(bar)
    assert reading.ally == 12 and reading.enemy is None


def test_rounds_from_scores_ignore_spurious_resets() -> None:
    from valorant_ai_coach.rules.recorder_life import rounds_from_scores

    ally = [(0, 0), (40, 0), (110, 1), (130, 1), (400, 3), (420, 3)]  # 1 -> 3: two rounds closed
    enemy = [(0, 0), (60, 0)]
    resets = [30.0, 100.0, 250.0, 330.0]  # 30: spurious flicker inside round 0
    starts = [r.start for r in rounds_from_scores([ally, enemy], resets)]
    assert starts == [0, 100.0, 250.0, 330.0]
    # A reset followed by a full 5 v 5 buy phase adds a round the score missed.
    extra = [r.start for r in rounds_from_scores([ally, enemy], resets, buy_phase_starts=[520.0])]
    assert extra[-1] == 520.0


def test_template_sources_must_be_train_recordings(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json
    import zipfile

    import pytest

    from valorant_ai_coach.knowledge.template_lineage import (
        TemplateSourceRefused,
        train_sources,
    )

    def archive(video_id: str) -> object:
        path = tmp_path / f"{video_id}.zip"
        with zipfile.ZipFile(path, "w") as handle:
            handle.writestr("index.json", json.dumps(
                {"video_id": video_id, "file_name": f"{video_id}.mp4", "size_bytes": 10}))
        return path

    sha = {"a": "1" * 64, "b": "2" * 64}
    registry = tmp_path / "dataset_registry.json"
    registry.write_text(json.dumps({"version": "v2", "seed": "s", "sources": [
        {"source_id": "a", "physical_match_id": "pa", "split": "TRAIN",
         "source_video_sha256": sha["a"]},
        {"source_id": "b", "physical_match_id": "pb", "split": "FROZEN_TEST",
         "source_video_sha256": sha["b"]}]}), encoding="utf-8")
    hashes = {v: {"file_name": f"{v}.mp4", "size_bytes": 10, "sha256": sha[v]} for v in sha}
    lineage, meta = train_sources(registry, [archive("a")], video_hashes=hashes)
    assert meta["split"] == "TRAIN" and lineage[0].source_video_sha256 == sha["a"]
    assert meta["sources"][0]["video_identity"] == "video_id+file_name+size+sha256"
    with pytest.raises(TemplateSourceRefused, match="DEV_COMPARISON"):
        train_sources(registry, [archive("a"), archive("b")])
    with pytest.raises(TemplateSourceRefused, match="not registered"):
        train_sources(registry, [archive("c")])
    wrong = {**hashes, "a": {**hashes["a"], "sha256": "3" * 64}}
    with pytest.raises(TemplateSourceRefused, match="does not match"):
        train_sources(registry, [archive("a")], video_hashes=wrong)


def test_round_phases_keep_score_buy_combat_and_end_apart() -> None:
    from valorant_ai_coach.rules.round_phases import PhaseSample, round_phases

    def at(sec: float, timer: int | None, ordinal: int, ally: int = 5, enemy: int = 5,
           planted: bool = False) -> PhaseSample:
        return PhaseSample(sec, timer, ordinal, ally, enemy, planted)

    samples = [at(0, 40, 0), at(10, 30, 0), at(20, 95, 0), at(60, 55, 0, 3, 0),  # eliminated
               at(70, None, 1, 5, 5), at(80, 22, 1), at(90, 97, 1), at(150, None, 1, planted=True),
               at(200, None, 2)]
    first, second, third = round_phases(samples)
    assert first.buy_phase_start == -5 and first.bases["buy_phase_start"] == "buy_countdown"
    assert first.combat_start == 15 and first.round_end == 60
    assert first.bases["round_end"] == "team_eliminated" and first.score_update is None
    assert second.score_update == 70 and second.buy_phase_start == 72  # 30 s buy countdown
    assert second.combat_start == 87
    # Planted, nobody eliminated: only the next score read bounds the end.
    assert second.round_end == 200 and second.bases["round_end"] == "score_update_upper_bound"
    assert third.combat_start is None


def test_top_bar_rows_feed_the_shared_timeline() -> None:
    from valorant_ai_coach.knowledge.score_reader import (
        GLYPH_SIZE,
        SCORE_WINDOWS,
        ScoreReader,
        glyph_boxes,
        normalise_glyph,
    )
    from valorant_ai_coach.knowledge.top_bar_timeline import (
        STREAM_KIND,
        TOP_BAR_ROI,
        top_bar_observation,
    )
    from valorant_ai_coach.temporal.game import DevelopmentGameTimeline

    def draw(text: str) -> np.ndarray:
        window = np.full((20, 40, 3), 60, np.uint8)
        cv2.putText(window, text, (8, 16), cv2.FONT_HERSHEY_PLAIN, 1.0, (255, 255, 255), 1)
        return window

    templates = np.zeros((10, GLYPH_SIZE[1], GLYPH_SIZE[0]), np.float32)
    for digit in range(10):
        gray, boxes = glyph_boxes(draw(str(digit)))
        templates[digit] = normalise_glyph(gray, boxes[0])
    reader = ScoreReader(templates)
    frame = np.full((1080, 1920, 3), 60, np.uint8)
    for side, text in (("ally", "7"), ("enemy", "12")):
        x0, y0, x1, y1 = SCORE_WINDOWS[side]
        big = cv2.resize(draw(text), (2 * (x1 - x0), 2 * (y1 - y0)),
                         interpolation=cv2.INTER_NEAREST)
        fx, fy = TOP_BAR_ROI[0] + 2 * x0, TOP_BAR_ROI[1] + 2 * y0
        frame[fy:fy + big.shape[0], fx:fx + big.shape[1]] = big
    sample = {"source_id": "s", "source_sha256": "a" * 64, "acquisition_id": "e",
              "native_epoch": "e", "native_pts_tick": 600, "native_time_base": "1/60",
              "acquired_frame_sha256": "b" * 64, "native_pixel_sha256": "c" * 64,
              "frame_size_px": [1920, 1080]}
    row = top_bar_observation(frame, sample, reader)
    assert row["context"]["score"] == [7, 12] and row["context"]["stream_kind"] == STREAM_KIND
    assert row["qualification"] == "development_only" and row["signals"] == []
    timeline = DevelopmentGameTimeline()
    timeline.add(row)  # the timeline accepts the row as an ordinary supplier observation


def test_kill_feed_death_needs_recorder_as_victim() -> None:
    other = FeedKill("enemy", "ally", "Clove", False, True)  # highlight, but victim is Clove
    own = FeedKill("enemy", "ally", "Omen", False, True)
    series = [_obs(0, "Omen", (1, 1, 1, 0), 5, 5, feed=()),
              _obs(5, "Omen", (1, 1, 1, 0), 4, 5, feed=(other,)),
              _obs(10, "Sova", (1, 1, 1, 0), 4, 5, feed=(other,)),
              _obs(15, "Omen", (1, 1, 1, 0), 3, 5, feed=(other, own)),
              _obs(20, "Sova", (1, 1, 1, 0), 3, 5, feed=(other, own))]
    derivation = derive(series, "Omen", "controller")
    deaths = derivation.reconciliation.deaths
    assert len(deaths) == 1 and deaths[0].sec >= 10  # nothing at 5 s (Clove's entry)
    assert derivation.reconciliation.dropped["kill_feed_other_victim"] == 1


def test_shots_from_magazine_drops() -> None:
    from valorant_ai_coach.rules.second_series import (
        SecondRecord,
        WeaponLimits,
        detect_shots,
        second_additions,
    )

    def rec(sec: float, magazine: int | None) -> SecondRecord:
        return SecondRecord(Observation(sec, True, "Omen", 0.9, (1, 1, 1, 0), 5, 5),
                            magazine, None, 0)

    limits = WeaponLimits(max_fire_rate=10.0, switch_magazines=frozenset({12}))
    records = [rec(0, 25), rec(1, 22), rec(2, None), rec(3, 20),  # gap of one unread second
               rec(4, 12),  # 20 -> 12: the pistol comes out, not 8 shots
               rec(5, 12), rec(10, 11),  # 5 s apart: not compared
               rec(11, 30), rec(12, 0)]  # reload, then a 30-round drop in 1 s: misread
    live = [True] * len(records)
    shots = detect_shots(records, live, limits=limits)
    assert [(s.sec, s.count, s.first) for s in shots] == [(1, 3, True), (3, 2, False)]
    assert detect_shots(records, [False] * len(records), limits=limits) == []
    additions = second_additions(records, live, limits)
    assert additions[1][0] == {"shot", "engagement_start"}
    assert additions[1][1] == {"first_shot_detected": True}  # no movement facts (gated off)


def test_detonation_wins_give_sides() -> None:
    from valorant_ai_coach.rules.side import outcome_sides

    rows = [(4, "ally", 100.0, 101.0, 146.0, 147.0, True),   # 45 s: detonation, ally attacked
            (5, "enemy", 200.0, 201.0, 246.0, 247.0, True),  # enemy detonated: ally defended
            (6, "ally", 300.0, 301.0, 320.0, 321.0, True),   # early end: not used
            (7, "ally", 400.0, 401.0, 446.0, 447.0, False)]  # someone eliminated: not used
    assert [(o.ordinal, o.side, o.source) for o in outcome_sides(rows)] == [
        (4, "attack", "detonation_win"), (5, "defense", "detonation_win")]


def test_promotion_needs_reviewed_independent_and_approved_evidence() -> None:
    from pathlib import Path

    from valorant_ai_coach.rules.qualification import (
        load_qualification,
        qualification,
        wilson_lower,
    )

    assert wilson_lower(160, 160) > 0.97 and wilson_lower(28, 30) < 0.8
    strong = {"reviewed": 400, "correct": 399, "coverage": 0.8}
    assert qualification({"development": strong, "independent": {**strong, "matches": 6},
                          "approval": "lead"})["qualified"]
    missing = qualification({"development": strong, "independent": {}, "approval": ""})
    assert not missing["qualified"]
    assert "independent: no INDEPENDENT_TEST evidence" in missing["missing"]
    assert "no approval recorded" in missing["missing"]
    report = load_qualification(Path("config/producer_qualification_v1.json"))
    assert report and not any(item["qualified"] for item in report.values())
