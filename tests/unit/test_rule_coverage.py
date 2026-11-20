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
    import hashlib
    import json
    import zipfile
    from types import SimpleNamespace

    import pytest

    from valorant_ai_coach.knowledge.template_lineage import (
        IDENTITY,
        IDENTITY_HASHED,
        TemplateSourceRefused,
        train_sources,
    )

    def archive(video_id: str, extra: bytes = b"") -> object:
        path = tmp_path / f"{video_id}.zip"
        with zipfile.ZipFile(path, "w") as handle:
            handle.writestr("index.json", json.dumps(
                {"video_id": video_id, "file_name": f"{video_id}.mp4", "size_bytes": 10}))
            if extra:
                handle.writestr("extra.bin", extra)
        return path

    sha = {"a": "1" * 64, "b": "2" * 64}
    sources = []
    for video_id, split in (("a", "TRAIN"), ("b", "FROZEN_TEST")):
        data = archive(video_id).read_bytes()
        sources.append({"source_id": video_id, "physical_match_id": f"p{video_id}",
                        "split": split, "source_video_sha256": sha[video_id],
                        "archive_sha256": hashlib.sha256(data).hexdigest(),
                        "archive_bytes": len(data)})
    registry = tmp_path / "dataset_registry.json"
    registry.write_text(json.dumps({"version": "v2", "seed": "s", "sources": sources}),
                        encoding="utf-8")

    def recording(video_id: str, **change: object) -> SimpleNamespace:
        fields = {"recording_id": f"rec_{video_id}", "source_sha256": sha[video_id],
                  "size_bytes": 10, "physical_match_id": f"p{video_id}",
                  "development_authorised": True, "independent_until_opened": False,
                  "locations": {"original": {"path": f"/videos/{video_id}.mp4",
                                             "size_bytes": 10}},
                  "learning": {"split": "TRAIN", "registry_source_id": video_id,
                               "registry_physical_match_id": f"p{video_id}",
                               "origin": "learning_registry:x"}}
        return SimpleNamespace(**{**fields, **change})

    def catalog(*records: SimpleNamespace) -> SimpleNamespace:
        index = {r.source_sha256: r for r in records}
        return SimpleNamespace(state=SimpleNamespace(head="h" * 64, by_sha=index.get))

    good = catalog(recording("a"), recording("b"))
    hashes = {v: {"file_name": f"{v}.mp4", "size_bytes": 10, "sha256": sha[v]} for v in sha}
    lineage, meta = train_sources(registry, [archive("a")], catalog=good, video_hashes=hashes)
    assert meta["split"] == "TRAIN" and lineage[0].source_video_sha256 == sha["a"]
    assert lineage[0].catalog_recording_id == "rec_a" and meta["catalog_journal_head"] == "h" * 64
    assert meta["sources"][0]["video_identity"] == IDENTITY_HASHED
    assert train_sources(registry, [archive("a")], catalog=good)[0][0].video_identity == IDENTITY
    with pytest.raises(TemplateSourceRefused, match="DEV_COMPARISON"):
        train_sources(registry, [archive("a"), archive("b")], catalog=good)
    with pytest.raises(TemplateSourceRefused, match="not registered"):
        train_sources(registry, [archive("c")], catalog=good)
    # A re-packed archive of the same recording is refused: its bytes are not registered.
    with pytest.raises(TemplateSourceRefused, match="archive bytes"):
        train_sources(registry, [archive("a", extra=b"more crops")], catalog=good)
    base = recording("a").learning
    refusals = {
        "not in the catalog": catalog(),
        "learning split is VALIDATION": catalog(recording("a", learning={**base,
                                                                         "split": "VALIDATION"})),
        "another registry source": catalog(recording("a", learning={**base,
                                                                    "registry_source_id": "z"})),
        "independent evaluation": catalog(recording("a", independent_until_opened=True)),
        "not authorised": catalog(recording("a", development_authorised=False)),
        "original recording": catalog(recording("a", locations={
            "original": {"path": "/videos/other.mp4", "size_bytes": 10}})),
    }
    for reason, refused in refusals.items():
        with pytest.raises(TemplateSourceRefused, match=reason):
            train_sources(registry, [archive("a")], catalog=refused)
    wrong = {**hashes, "a": {**hashes["a"], "sha256": "3" * 64}}
    with pytest.raises(TemplateSourceRefused, match="does not match"):
        train_sources(registry, [archive("a")], catalog=good, video_hashes=wrong)


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
    # The same row reaches hud_observations, the fields the #164 promoter reads.
    from valorant_ai_coach.temporal.application import _hud

    hud = _hud([row])
    ally = hud["ally_score"]["candidates"]
    assert [c["value"] for c in ally] == [7] and 0.75 <= ally[0]["confidence"] <= 1.0
    assert [c["value"] for c in hud["enemy_score"]["candidates"]] == [12]
    assert ally[0]["subject"] == "viewed_HUD; recorder_ownership_unresolved"


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


def test_shots_stay_inside_one_round_and_one_weapon() -> None:
    from valorant_ai_coach.rules.second_series import (
        SecondRecord,
        WeaponLimits,
        detect_shots,
        movement_changes,
    )

    def rec(sec: float, magazine: int | None, reserve: int | None = None,
            residual: float | None = None) -> SecondRecord:
        return SecondRecord(Observation(sec, True, "Omen", 0.9, (1, 1, 1, 0), 5, 5),
                            magazine, residual, 40, reserve)

    limits = WeaponLimits(max_fire_rate=10.0, switch_magazines=frozenset({12}))
    records = [rec(0, 25, 50), rec(1, 22, 50),
               rec(2, 18, 36),  # reserve 50 -> 36: switched to another gun, not 4 shots
               rec(3, 15, 36),  # a real shot with the new gun
               rec(4, 14), rec(5, 12),  # round ends between 4 and 5: not compared
               rec(6, 10), rec(7, 8)]
    live = [True] * len(records)
    rounds: list[int | None] = [0, 0, 0, 0, 0, None, 1, 1]
    shots = detect_shots(records, live, limits=limits, segments=rounds)
    assert [(s.sec, s.count, s.first) for s in shots] == [
        (1, 3, True), (3, 3, False), (4, 1, False), (7, 2, True)]  # new round: first again
    # Where the timeline has no round (None), readings still pair, but not across
    # a round clock restart.
    clock = [SecondRecord(Observation(t, True, "Omen", 0.9, (1, 1, 1, 0), 5, 5, timer=c),
                          m, None, 40) for t, c, m in ((0, 3, 20), (1, 99, 18), (2, 98, 15))]
    assert [s.sec for s in detect_shots(clock, [True] * 3, limits=limits,
                                        segments=[None] * 3)] == [2]
    # Without round segments the pair across the boundary would have counted.
    assert (5, 2) in [(s.sec, s.count) for s in detect_shots(records, live, limits=limits)]
    moves = [rec(t, None, residual=r) for t, r in enumerate([1, 5, 5, 1, 5])]
    assert [c.sec for c in movement_changes(moves, [True] * 5, [0, 0, 0, 1, 1])] == [1, 4]


def test_detonation_wins_give_sides() -> None:
    from valorant_ai_coach.rules.side import outcome_sides

    rows = [(4, "ally", 100.0, 101.0, 146.0, 147.0, True),   # 45 s: detonation, ally attacked
            (5, "enemy", 200.0, 201.0, 246.0, 247.0, True),  # enemy detonated: ally defended
            (6, "ally", 300.0, 301.0, 320.0, 321.0, True),   # early end: not used
            (7, "ally", 400.0, 401.0, 446.0, 447.0, False)]  # someone eliminated: not used
    assert [(o.ordinal, o.side, o.source) for o in outcome_sides(rows)] == [
        (4, "attack", "detonation_win"), (5, "defense", "detonation_win")]


def test_producer_evaluations_are_records_not_a_promotion_path() -> None:
    import json
    from pathlib import Path

    data = json.loads(Path("config/producer_evaluation_v1.json").read_text(encoding="utf-8"))
    assert set(data["evaluation_classes"]) == {
        "development", "promoted_from_shared_timeline", "independently_qualified"}
    for entry in data["producers"].values():
        # Development numbers come from exposed recordings; nothing is qualified here.
        assert entry["independent_evaluation"] == {"matches": 0, "status": "not_run"}
        assert not {"qualified", "approval", "promote"} & set(entry)


def test_own_view_rows_feed_hud_observations() -> None:
    from valorant_ai_coach.knowledge.ammo_reader import GLYPH_SIZE as AMMO_GLYPH
    from valorant_ai_coach.knowledge.ammo_reader import AmmoReader
    from valorant_ai_coach.knowledge.own_view_timeline import (
        magazine_observation,
        spike_carrier_observation,
    )
    from valorant_ai_coach.knowledge.spike_carrier import INVENTORY_ROI, SpikeCarrierReader
    from valorant_ai_coach.temporal.application import _hud
    from valorant_ai_coach.temporal.game import DevelopmentGameTimeline

    rng = np.random.default_rng(7)
    patch = cv2.GaussianBlur(rng.integers(0, 255, (26, 40)).astype(np.uint8), (3, 3), 0)
    frame = np.full((1080, 1920, 3), 40, np.uint8)
    x, y = INVENTORY_ROI[0] + 2 * 50, INVENTORY_ROI[1] + 2 * 10
    big = cv2.resize(patch, (80, 52), interpolation=cv2.INTER_NEAREST)
    frame[y:y + 52, x:x + 80] = big[:, :, None]
    sample = {"source_id": "s", "source_sha256": "a" * 64, "acquisition_id": "e",
              "native_epoch": "e", "native_pts_tick": 600, "native_time_base": "1/60",
              "acquired_frame_sha256": "b" * 64, "native_pixel_sha256": "c" * 64,
              "frame_size_px": [1920, 1080]}
    spike = spike_carrier_observation(frame, sample, SpikeCarrierReader(patch))
    ammo = magazine_observation(frame, sample, AmmoReader(
        np.ones((10, AMMO_GLYPH[1], AMMO_GLYPH[0]), np.float32)))
    timeline = DevelopmentGameTimeline()
    for row in (spike, ammo):
        assert row["signals"] == [] and row["qualification"] == "development_only"
        timeline.add(row)
    hud = _hud([spike, ammo])
    carried = hud["spike_carried"]["candidates"]
    assert [c["value"] for c in carried] == [True] and carried[0]["confidence"] > 0.9
    assert hud["ammo"]["status"] == "UNKNOWN" and "ammo_current" not in hud  # nothing read


def test_second_death_needs_a_revive_and_no_new_round() -> None:
    from valorant_ai_coach.rules.recorder_life import (
        Round,
        ally_revives,
        buy_phase_restarts,
        combat_starts,
        reconcile,
        score_rises,
    )

    rounds = [Round(0.0, 300.0)]  # the round source merged two rounds
    live = [float(t) for t in range(20, 60)]
    # Seen alive long after a "death" with no ally coming back: the first was false.
    plain = reconcile(rounds, {"kill_feed": [10.0, 60.0]}, live_samples=live, revives=[])
    assert [(d.sec, d.after_revive) for d in plain.deaths] == [(60.0, False)]
    assert plain.dropped["superseded"] == 1
    # The allied count went up in between: a revive.
    revived = reconcile(rounds, {"kill_feed": [10.0, 60.0]}, live_samples=live,
                        revives=ally_revives([(14.0, 3), (15.0, 4), (16.0, 3)]))
    assert [d.after_revive for d in revived.deaths] == [False, True]
    # A new round's combat clock in between: two rounds, two deaths, no revive.
    clock = [(30.0, 3), (31.0, 99), (32.0, 98)]
    assert combat_starts(clock) == [31.0]
    split = reconcile(rounds, {"kill_feed": [10.0, 60.0]}, restarts=combat_starts(clock))
    assert [(d.sec, d.after_round_restart) for d in split.deaths] == [(10.0, False),
                                                                     (60.0, True)]
    assert buy_phase_restarts([(20.0, 4), (25.0, 28), (27.0, 26)]) == [53.0]
    assert score_rises([(0, 1, 1), (1, 1, 1), (2, 2, 1), (3, 2, 1)]) == [22.0]
    assert ally_revives([(0.0, 2), (1.0, 5)]) == []  # a full team is a new round


def test_ammo_changes_tell_shots_reloads_and_switches_apart() -> None:
    from valorant_ai_coach.rules.second_series import (
        SecondRecord,
        WeaponLimits,
        ammo_events,
        classify_ammo_change,
    )

    def rec(sec: float, magazine: int | None, reserve: int | None) -> SecondRecord:
        return SecondRecord(Observation(sec, True, "Omen", 0.9, (1, 1, 1, 0), 5, 5),
                            magazine, None, 40, reserve)

    limits = WeaponLimits(max_fire_rate=10.0, switch_magazines=frozenset({12}))
    assert classify_ammo_change(rec(0, 25, 50), rec(1, 22, 50), limits) == "shot"
    assert classify_ammo_change(rec(0, 11, 50), rec(1, 25, 36), limits) == "reload"
    # Rounds fired just before reloading come out of the old magazine only.
    assert classify_ammo_change(rec(0, 20, 50), rec(1, 25, 42), limits) == "reload"
    assert classify_ammo_change(rec(0, 11, 50), rec(1, 12, 36), limits) == "weapon_switch"
    assert classify_ammo_change(rec(0, 8, 24), rec(1, 5, 20), limits) == "weapon_switch"
    assert classify_ammo_change(rec(0, 25, None), rec(1, 12, None), limits) == "weapon_switch"
    assert classify_ammo_change(rec(0, 12, None), rec(1, 8, None), limits) == "shot"
    assert classify_ammo_change(rec(0, 5, None), rec(1, 25, None), limits) == "rise_unexplained"
    assert classify_ammo_change(rec(0, 25, 50), rec(1, 2, 50), limits) == "misread"
    # A lone reserve misread ("60" cut to "0") with the magazine unchanged is no switch.
    records = [rec(0, 23, 60), rec(1, 23, 0), rec(2, 23, 60), rec(3, 23, 60)]
    assert ammo_events(records, [True] * 4, limits) == []
    switched = [rec(0, 25, 50), rec(1, 25, 50), rec(2, 25, 36), rec(3, 25, 36)]
    assert [e.kind for e in ammo_events(switched, [True] * 4, limits)] == ["weapon_switch"]


def test_engagement_motion_places_the_first_shot_frame() -> None:
    from valorant_ai_coach.rules.engagement_motion import (
        MotionFrame,
        engagement_motion,
        first_shot_frame,
        moving_over,
    )

    def frame(k: int, magazine: int | None, h_err: float = 0.1,
              lag: int = 150) -> MotionFrame:
        return MotionFrame(10 + k / 60, 150, lag, h_err, 0.05, 0.0, 0.0, magazine)

    frames = [frame(k, 25) for k in range(40)] + [frame(40, 24), frame(41, 24),
                                                   frame(42, 24), frame(43, 24)]
    assert abs(first_shot_frame(frames, 10.2, 11.0) - (10 + 40 / 60)) < 1e-9
    # A one-frame flicker is not a shot.
    flicker = [frame(k, 25) for k in range(20)] + [frame(20, 22)] + \
        [frame(k, 25) for k in range(21, 30)]
    assert first_shot_frame(flicker, 10.0, 10.5) is None
    assert engagement_motion(flicker, 10.0, 10.5) is None
    # The rule only ever says "moving"; still frames give None, never False.
    still = [frame(k, 25) for k in range(40)]
    assert moving_over(still, still[-1].sec) is None
    busy = [frame(k, 25, h_err=1.5, lag=20) for k in range(40)]
    assert moving_over(busy, busy[-1].sec) is True
    shot = engagement_motion(busy + [frame(40, 24, 1.5, 20), frame(41, 24, 1.5, 20),
                                     frame(42, 24, 1.5, 20)], 10.3, 11.0)
    assert shot is not None and shot.moving_before_shot is True
