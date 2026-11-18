"""Promote #153/#155 knowledge-reader observations into confirmed Rounds.

``TimelinePromoter`` confirms Round boundaries, deaths and HUD snapshots from the
shared timeline. The per-second knowledge-reader observations of #153/#155
(``scripts/knowledge/extract_second_features.py``: top-bar alive counts, ability
HUD charges, kill feed, spike header) carry the facts the shared timeline does not:
``numbers_state``, ``utility_available_count``, ``first_death_by_player``, ``side``
and ``player_role``.

This module adds them to the Rounds the timeline already confirmed. It has no
recognition and no state machine of its own:

* Time, Round membership, the recorder's own live view and deaths come from the
  shared timeline only. A reading is used only in a second of a confirmed Round
  window, and an own-view reading (charges, spike header) only in a second the
  timeline observed as the recorder's own view while alive.
* The observations must come from the same recording as the timeline (same
  source SHA-256), otherwise nothing is promoted.
* Ownership: the recorder's agent is the majority agent of the ability HUD over
  the timeline's own live seconds; charges are used only when the HUD shows that
  agent. Kill-feed recorder entries need the game's own-player highlight and, when
  the victim portrait was identified, the recorder's agent.
* A death stays the timeline's. Elimination order comes from the top-bar alive
  counts, which only decrease by eliminations. The kill feed never creates or
  removes an elimination: each new feed entry is assigned to at most one top-bar
  drop of its victim's team (exclusive use), entries left over are reported as
  phantom, and only an assigned entry can name the recorder as killer or victim or
  order two eliminations read in the same second. Revives (own live view again
  after a death) and DOWNED seconds are reported apart from deaths.
* A frame image is one piece of evidence. Keyframes whose acquired frame was
  already used at an earlier time (static frames) are dropped, so a repeated
  image never supports its own stability check.

Field confidences are policy constants for readings that passed the stability and
consistency gates (``config/timeline_promotion_v1.json`` ``second_features``).
They are development values (``promoted_from_shared_timeline``), not
``independently_qualified``.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from valorant_ai_coach.events.source_contract import EventSourceContract
from valorant_ai_coach.knowledge import GameKnowledge, load_game_knowledge
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rules.development_readiness import FEED_REPEAT_SEC, FeedKill, Observation
from valorant_ai_coach.rules.second_series import SecondRecord, load_second_records
from valorant_ai_coach.rules.side import ATTACK, SideObservation, infer_sides

from .timeline_promotion import (
    _OBSERVED,
    FORMAL_QUALIFICATION,
    PromotionError,
    PromotionResult,
    RoundPromotion,
    SecondView,
    TimelinePromoter,
    TimelineView,
)

PRODUCER = "second_feature_promotion_v1"
_CHARGE_AVAILABLE = 0.25  # same split as #155 development_readiness


@dataclass(frozen=True, slots=True)
class FeedArrival:
    """One new kill-feed entry, at the sample where it first appears.

    ``kind`` is ``elimination`` (counted by the killer's team; the victim is the
    other team) or ``highlight`` (the own-player highlight on the killer or the
    victim side, counted apart because it flickers independently of the row).
    """

    sec: float
    kind: str
    killer_team: str
    victim_team: str
    recorder_killer: bool = False
    recorder_victim: bool = False


_OTHER_TEAM = {"ally": "enemy", "enemy": "ally"}


def _arrivals(
    series: Sequence[Observation], keys: Any, repeat_sec: float,
) -> list[tuple[float, Any]]:
    out: list[tuple[float, Any]] = []
    history: list[tuple[float, Counter[Any]]] = []
    for obs in series:
        if obs.feed is None:
            continue
        history = [(t, c) for t, c in history if obs.sec - t <= repeat_sec]
        now: Counter[Any] = Counter(key for kill in obs.feed for key in keys(kill))
        for key, count in sorted(now.items(), key=lambda kv: str(kv[0])):
            before = max((c[key] for _, c in history), default=0)
            out.extend((obs.sec, key) for _ in range(count - before))
        history.append((obs.sec, now))
    return out


def feed_arrivals(
    series: Sequence[Observation], repeat_sec: float = FEED_REPEAT_SEC,
) -> list[FeedArrival]:
    """New kill-feed entries, counted by multiplicity.

    Entries persist in the feed for several seconds, drop out of single reads, and
    the victim's team colour, the victim name and the own-player highlight flicker
    from read to read. So an entry is keyed by its killer's team only (the
    highlight fixes the recorder's side to ``ally``), and an arrival is counted when
    the number of entries with that key in a read exceeds the most seen in any read
    of the previous ``repeat_sec`` seconds. Highlights are counted the same way in a
    stream of their own.
    """

    def killer(kill: FeedKill) -> list[str]:
        team = "ally" if kill.recorder_killer else kill.killer_team
        return [team] if team in _OTHER_TEAM else []

    def highlight(kill: FeedKill) -> list[str]:
        if kill.recorder_victim and not kill.recorder_killer:
            return ["victim"]
        if kill.recorder_killer and not kill.recorder_victim:
            return ["killer"]
        return []

    out = [
        FeedArrival(sec, "elimination", team, _OTHER_TEAM[team])
        for sec, team in _arrivals(series, killer, repeat_sec)
    ]
    for sec, side in _arrivals(series, highlight, repeat_sec):
        out.append(FeedArrival(
            sec, "highlight", "enemy" if side == "victim" else "ally",
            "ally" if side == "victim" else "enemy",
            recorder_killer=side == "killer", recorder_victim=side == "victim",
        ))
    return sorted(out, key=lambda a: (a.sec, a.kind))


@dataclass(frozen=True, slots=True)
class SecondFeaturePolicy:
    agent_min_score: float
    agent_min_frames: int
    agent_min_share: float
    alive_confidence: float
    alive_increase_hold_sec: int
    utility_confidence: float
    kill_confidence: float
    feed_match_window_sec: float
    feed_repeat_sec: float
    top_bar_min_coverage: float
    death_drop_before_sec: int
    death_drop_after_sec: int
    death_feed_lookback_sec: int
    recovered_death_confidence: float
    spike_clear_score: float
    revive_min_live_sec: int
    snapshot_min_interval_sec: int
    score_min_reads: int
    score_min_share: float
    enemy_eco_confidence: float

    @classmethod
    def load(cls, path: Path | None = None) -> SecondFeaturePolicy:
        source = path or resource_path("config/timeline_promotion_v1.json")
        raw = json.loads(Path(source).read_text(encoding="utf-8"))["second_features"]
        policy = cls(
            agent_min_score=float(raw["agent_min_score"]),
            agent_min_frames=int(raw["agent_min_frames"]),
            agent_min_share=float(raw["agent_min_share"]),
            alive_confidence=float(raw["alive_confidence"]),
            alive_increase_hold_sec=int(raw["alive_increase_hold_sec"]),
            utility_confidence=float(raw["utility_confidence"]),
            kill_confidence=float(raw["kill_confidence"]),
            feed_match_window_sec=float(raw["feed_match_window_sec"]),
            feed_repeat_sec=float(raw["feed_repeat_sec"]),
            top_bar_min_coverage=float(raw["top_bar_min_coverage"]),
            death_drop_before_sec=int(raw["death_drop_before_sec"]),
            death_drop_after_sec=int(raw["death_drop_after_sec"]),
            death_feed_lookback_sec=int(raw["death_feed_lookback_sec"]),
            recovered_death_confidence=float(raw["recovered_death_confidence"]),
            spike_clear_score=float(raw["spike_clear_score"]),
            revive_min_live_sec=int(raw["revive_min_live_sec"]),
            snapshot_min_interval_sec=int(raw["snapshot_min_interval_sec"]),
            score_min_reads=int(raw["score_min_reads"]),
            score_min_share=float(raw["score_min_share"]),
            enemy_eco_confidence=float(raw["enemy_eco_confidence"]),
        )
        for name in (
            "alive_confidence", "utility_confidence", "kill_confidence", "enemy_eco_confidence"
        ):
            if not 0.0 < getattr(policy, name) <= 1.0:
                raise PromotionError(f"second_features.{name} は (0, 1] で指定してください")
        return policy


@dataclass(slots=True)
class SecondFeatureReport:
    recorder_agent: str | None = None
    recorder_role: str = "unknown"
    agent_share: float = 0.0
    side_status: str = "unobserved"
    first_half_side: str | None = None
    counts: Counter[str] = field(default_factory=Counter)
    rejected: Counter[str] = field(default_factory=Counter)
    per_round: dict[int, dict[str, Any]] = field(default_factory=dict)
    checks: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "producer": PRODUCER,
            "independent_qualification": "not_met_development_only",
            "recorder_agent": self.recorder_agent,
            "recorder_role": self.recorder_role,
            "agent_share": round(self.agent_share, 3),
            "side_status": self.side_status,
            "first_half_side": self.first_half_side,
            "counts": dict(sorted(self.counts.items())),
            "rejected": dict(sorted(self.rejected.items())),
            "cross_reader_checks": self.checks,
            "rounds": [
                {"round_no": number, **values}
                for number, values in sorted(self.per_round.items())
            ],
        }


def load_records(path: Path) -> list[SecondRecord]:
    """Read ``extract_second_features.py`` output (.jsonl or .jsonl.gz)."""
    if path.suffix == ".gz":
        import gzip
        import tempfile

        with gzip.open(path, "rt", encoding="utf-8") as stream:
            text = stream.read()
        with tempfile.TemporaryDirectory() as directory:
            plain = Path(directory) / "features.jsonl"
            plain.write_text(text, encoding="utf-8")
            return load_second_records(plain)
    return load_second_records(path)


def load_frame_refs(path: Path) -> dict[float, str]:
    """``sec`` -> ``frame:<acquired_frame_sha256>`` of each feature record."""
    import gzip

    refs: dict[float, str] = {}
    text_open = gzip.open if path.suffix == ".gz" else open
    with text_open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            digest = (row.get("sample") or {}).get("acquired_frame_sha256")
            if digest:
                refs[float(row["sec"])] = f"frame:{digest}"
    return refs


def records_source_sha256(path: Path) -> str | None:
    import gzip

    text_open = gzip.open if path.suffix == ".gz" else open
    with text_open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                sample = json.loads(line).get("sample") or {}
                value = sample.get("source_sha256")
                return str(value) if value else None
    return None


class SecondFeaturePromoter:
    """Add knowledge-reader facts to Rounds confirmed by ``TimelinePromoter``."""

    def __init__(
        self,
        policy: SecondFeaturePolicy | None = None,
        *,
        knowledge: GameKnowledge | None = None,
    ) -> None:
        self.policy = policy or SecondFeaturePolicy.load()
        self.knowledge = knowledge or load_game_knowledge()
        self.contract = EventSourceContract.load(
            resource_path("config/event_source_contract_v1.json")
        )

    # -- entry point ---------------------------------------------------------------

    def augment(
        self,
        bundle: Mapping[str, Any],
        result: PromotionResult,
        records: Sequence[SecondRecord],
        *,
        records_sha256: str | None,
        frame_refs: Mapping[float, str] | None = None,
    ) -> SecondFeatureReport:
        report = SecondFeatureReport()
        self._refs: dict[int, str] = {}
        self._timeline_refs: dict[int, tuple[str, ...]] = {}
        source = (bundle.get("source") or {}).get("source_sha256")
        if not source or records_sha256 != source:
            raise PromotionError("特徴量と共通タイムラインの元動画（SHA-256）が一致しません")
        view = TimelineView(bundle)
        by_second: dict[int, Observation] = {}
        used_frames: set[str] = set()
        for record in sorted(records, key=lambda r: r.observation.sec):
            # Timeline second s covers [s, s + 1); keyframes fall anywhere inside it.
            second = math.floor(record.observation.sec)
            if not 0 <= second < len(view):
                continue
            ref = (frame_refs or {}).get(float(record.observation.sec))
            if ref and ref in used_frames:
                # The same image already counted at an earlier time (static frame).
                report.counts["reused_frame_readings_dropped"] += 1
                continue
            if second in by_second:
                report.counts["second_duplicate_readings"] += 1
                continue
            by_second[second] = record.observation
            if ref:
                used_frames.add(ref)
                self._refs[second] = ref
        report.counts["aligned_seconds"] = len(by_second)
        agent = self._recorder_agent(view, by_second, report)
        role = "unknown"
        if agent is not None:
            known = self.knowledge.agent(agent)
            role = known.role if known is not None else "unknown"
        report.recorder_agent, report.recorder_role = agent, role
        self._timeline_refs = {
            row.index: row.evidence_refs for row in view.seconds if row.evidence_refs
        }
        feed_new = feed_arrivals(
            [by_second[s] for s in sorted(by_second)], self.policy.feed_repeat_sec
        )
        report.counts["feed_arrivals"] = len(feed_new)
        self._feed_refs = {
            index: self._refs[int(arrival.sec)]
            for index, arrival in enumerate(feed_new) if int(arrival.sec) in self._refs
        }
        sides = self._sides(view, by_second, result, agent, report)
        for item in result.rounds:
            if not item.confirmed:
                continue
            assert item.window is not None and item.start is not None and item.end is not None
            stats: dict[str, Any] = {}
            if agent is not None:
                item.round_meta["player_agent"] = agent
                item.round_meta["player_role"] = role
            side = sides.get(item.round_no)
            if side is not None:
                item.round_meta["side"] = side[0]
                stats["side"] = list(side)
                report.counts["rounds_with_side"] += 1
            self._snapshots(view, by_second, item, agent, report, stats)
            self._recover_deaths(view, by_second, item, report, stats)
            self._eliminations(view, by_second, feed_new, item, report, stats)
            self._revives_and_downed(view, item, report, stats)
            item.events.sort(key=_event_order)
            for event in item.events:
                if event["type"] in {"kill", "state_snapshot"}:
                    self.contract.validate_event(
                        event, "hud_analyzer" if event["type"] == "kill"
                        else "derived_event_builder"
                    )
            report.per_round[item.round_no] = stats
        self._enemy_economy(by_second, result, report)
        report.checks = self._checks(by_second, feed_new, result, agent, sides, report)
        return report

    # -- cross-reader consistency ---------------------------------------------------------

    def _checks(
        self, by_second: Mapping[int, Observation],
        feed_new: Sequence[FeedArrival], result: PromotionResult,
        agent: str | None, sides: Mapping[int, tuple[str, str]],
        report: SecondFeatureReport,
    ) -> dict[str, dict[str, int]]:
        """Consistency between different readers of the same recording (not labels).

        * ``top_bar_vs_kill_feed``: per Round, every top-bar elimination got its own
          kill-feed entry and no feed entry was left over (``counts`` has the totals
          of assigned, missing and phantom entries).
        * ``recorder_death_vs_kill_feed``: the feed entry assigned to the recorder's
          death drop carries the own-player highlight on the victim side.
        * ``first_death_vs_kill_feed``: a recorder death derived as first (not first)
          must (must not) be the earliest assigned feed entry of the Round.
        * ``recorder_death_recall``: a Round whose top bar shows the recorder's team
          at 0 must have a promoted recorder death (``missed`` otherwise).
        * ``side_defense``: a Round given ``defense`` must show no spike header in the
          recorder's own view at all.
        """
        counts: dict[str, Counter[str]] = {
            k: Counter() for k in (
                "top_bar_vs_kill_feed", "recorder_death_vs_kill_feed",
                "first_death_vs_kill_feed", "recorder_death_recall", "side_defense",
            )
        }
        for item in result.rounds:
            if not item.confirmed:
                continue
            assert item.window is not None and item.start is not None and item.end is not None
            stats = report.per_round.get(item.round_no, {})
            if "top_bar_eliminations" in stats:
                counts["top_bar_vs_kill_feed"][
                    "agree" if stats["top_bar_eliminations"] == stats["feed_assigned"]
                    and stats["feed_phantom"] == 0 else "disagree"
                ] += 1
            deaths = [e for e in item.events if e["type"] == "player_death"]
            kills = [e for e in item.events if e["type"] == "kill"]
            feed_secs = [
                float(e["attributes"]["feed_sec"]) for e in kills
                if "feed_sec" in e["attributes"]
            ]
            for death in deaths:
                attribution = death["attributes"].get("kill_feed_attribution")
                proof = death["attributes"]["evidence_provenance"]
                if attribution == "recorder_victim":
                    counts["recorder_death_vs_kill_feed"]["agree"] += 1
                elif attribution == "conflict":
                    counts["recorder_death_vs_kill_feed"]["disagree"] += 1
                elif attribution is not None:
                    counts["recorder_death_vs_kill_feed"]["undetermined"] += 1
                if proof.get("elimination_coverage") != "top_bar_alive_counts":
                    continue
                first = _first_elimination(death, kills)
                if "feed_sec" not in proof:
                    counts["first_death_vs_kill_feed"]["undetermined"] += 1
                    continue
                feed_first = all(float(proof["feed_sec"]) < sec for sec in feed_secs)
                counts["first_death_vs_kill_feed"][
                    "agree" if feed_first == first else "disagree"
                ] += 1
            wiped = any(
                (pair := _bar_pair(by_second.get(s))) is not None and pair[0] == 0
                and _bar_pair(by_second.get(s + 1)) == pair
                for s in range(item.start.time_sec, item.end.time_sec + 1)
            )
            if wiped:
                counts["recorder_death_recall"]["found" if deaths else "missed"] += 1
            side = sides.get(item.round_no)
            if side is not None and side[0] == "defense":
                seen = any(
                    (obs := by_second.get(s)) is not None and obs.spike_carried
                    and self._own_hud(obs, agent)
                    for s in range(item.window[0], item.end.time_sec)
                )
                counts["side_defense"]["disagree" if seen else "agree"] += 1
        return {k: dict(sorted(v.items())) for k, v in counts.items()}

    # -- ownership -------------------------------------------------------------------

    @staticmethod
    def _own_live(row: SecondView | None) -> bool:
        return row is not None and (row.camera_value, row.camera_status) == (
            "SELF", _OBSERVED
        ) and (row.life_value, row.life_status) == ("ALIVE", _OBSERVED)

    def _recorder_agent(
        self, view: TimelineView, by_second: Mapping[int, Observation],
        report: SecondFeatureReport,
    ) -> str | None:
        votes: Counter[str] = Counter()
        for second, obs in by_second.items():
            if not self._own_live(view.row(second)):
                continue
            if obs.hud_present and obs.viewed_agent and (
                obs.viewed_score >= self.policy.agent_min_score
            ):
                votes[obs.viewed_agent] += 1
        total = sum(votes.values())
        if total < self.policy.agent_min_frames:
            report.rejected["recorder_agent_too_few_frames"] += 1
            return None
        agent, count = votes.most_common(1)[0]
        report.agent_share = count / total
        if report.agent_share < self.policy.agent_min_share:
            report.rejected["recorder_agent_not_dominant"] += 1
            return None
        return agent

    def _own_hud(self, obs: Observation | None, agent: str | None) -> bool:
        return (
            obs is not None and agent is not None and obs.hud_present
            and obs.viewed_agent == agent and obs.viewed_score >= self.policy.agent_min_score
        )

    # -- side --------------------------------------------------------------------------

    def _sides(
        self, view: TimelineView, by_second: Mapping[int, Observation],
        result: PromotionResult, agent: str | None, report: SecondFeatureReport,
    ) -> dict[int, tuple[str, str]]:
        """Attack rounds from the spike header in the recorder's own live view (only
        attackers carry the spike), extended by the half structure (#155 side.py)."""
        sightings: dict[int, list[float]] = {}
        for item in result.rounds:
            if not item.confirmed:
                continue
            assert item.start is not None and item.end is not None and item.window is not None
            for second in range(item.window[0], item.end.time_sec):
                obs = by_second.get(second)
                if (
                    obs is not None and obs.spike_carried
                    and self._own_live(view.row(second)) and self._own_hud(obs, agent)
                ):
                    sightings.setdefault(item.round_no - 1, []).append(obs.spike_score or 0.0)
        observations = [
            SideObservation(ordinal, ATTACK, "spike_carried")
            for ordinal, scores in sightings.items()
            if len(scores) >= 2 or max(scores) >= self.policy.spike_clear_score
        ]
        rules_per_half = int(self.knowledge.rule("regulation_rounds_per_half"))
        inference = infer_sides(observations, rounds_per_half=rules_per_half)
        report.side_status = inference.status
        report.first_half_side = inference.first_half_side
        report.counts["side_observations"] = len(observations)
        if inference.status == "conflict":
            report.rejected["side_conflict"] += 1
            return {}
        out: dict[int, tuple[str, str]] = {}
        for item in result.rounds:
            side = inference.side(item.round_no - 1)
            if side is not None:
                out[item.round_no] = side
        return out

    # -- alive counts and utility ----------------------------------------------------------

    def _snapshots(
        self, view: TimelineView, by_second: Mapping[int, Observation],
        item: RoundPromotion, agent: str | None, report: SecondFeatureReport,
        stats: dict[str, Any],
    ) -> None:
        assert item.window is not None
        accepted_alive: tuple[int, int] | None = None
        alive_by_second: dict[int, tuple[int, int]] = {}
        utility_by_second: dict[int, int] = {}
        for second in range(item.window[0], item.window[1]):
            obs = by_second.get(second)
            if obs is None or not self._own_live(view.row(second)):
                continue
            pair = _alive_pair(obs)
            if pair is not None:
                stable = any(_alive_pair(by_second.get(second + d)) == pair for d in (-1, 1))
                if not stable:
                    report.rejected["alive_unstable"] += 1
                elif accepted_alive is not None and (
                    pair[0] > accepted_alive[0] or pair[1] > accepted_alive[1]
                ) and not all(
                    _alive_pair(by_second.get(second + d)) == pair
                    for d in range(self.policy.alive_increase_hold_sec)
                ):
                    report.rejected["alive_increase_unconfirmed"] += 1
                else:
                    alive_by_second[second] = pair
                    accepted_alive = pair
            elif obs.ally_alive is not None or obs.enemy_alive is not None:
                report.rejected["alive_out_of_range"] += 1
            if self._own_hud(obs, agent):
                count = _utility_count(obs)
                stable = any(
                    self._own_hud(by_second.get(second + d), agent)
                    and _utility_count(by_second[second + d]) == count
                    for d in (-1, 1) if (second + d) in by_second
                )
                if stable:
                    utility_by_second[second] = count
                else:
                    report.rejected["utility_unstable"] += 1
            elif obs.hud_present and agent is not None:
                report.rejected["utility_hud_not_recorder"] += 1
        existing = {int(s["time_sec"]): s for s in item.snapshots}
        added = 0
        last: tuple[Any, Any] | None = None
        last_at = -10**9
        for second in sorted(set(alive_by_second) | set(utility_by_second)):
            snapshot = existing.get(second)
            state = (alive_by_second.get(second), utility_by_second.get(second))
            if snapshot is None and state == last and (
                second - last_at < self.policy.snapshot_min_interval_sec
            ):
                continue  # unchanged and recent: no new snapshot second
            last, last_at = state, second
            if snapshot is None:
                snapshot = _empty_snapshot(second)
                existing[second] = snapshot
                item.snapshots.append(snapshot)
                added += 1
            confidence = snapshot.setdefault("source_confidence", {})
            if second in alive_by_second:
                snapshot["ally_alive"], snapshot["enemy_alive"] = alive_by_second[second]
                confidence["ally_alive"] = confidence["enemy_alive"] = (
                    self.policy.alive_confidence
                )
            if second in utility_by_second:
                snapshot["utility_available_count"] = utility_by_second[second]
                confidence["utility_available_count"] = self.policy.utility_confidence
        item.snapshots.sort(key=lambda s: float(s["time_sec"]))
        for event in item.events:
            second = int(event["time_sec"])
            if event["type"] == "state_snapshot" and (
                second in alive_by_second or second in utility_by_second
            ) and second in self._refs:
                refs = event["attributes"]["evidence_provenance"]["evidence_refs"]
                if self._refs[second] not in refs:
                    refs.append(self._refs[second])
        self._snapshot_events(item, added)
        stats.update({"alive_seconds": len(alive_by_second),
                      "utility_seconds": len(utility_by_second)})
        report.counts["alive_seconds"] += len(alive_by_second)
        report.counts["utility_seconds"] += len(utility_by_second)

    def _snapshot_events(self, item: RoundPromotion, added: int) -> None:
        """One state_snapshot Event per snapshot second (existing ones are kept)."""
        if not added:
            return
        refs = {
            second: (ref, *self._timeline_refs.get(second, ()))
            for second, ref in self._refs.items()
        }
        have = {int(e["time_sec"]) for e in item.events if e["type"] == "state_snapshot"}
        for snapshot in item.snapshots:
            second = int(snapshot["time_sec"])
            if second in have:
                continue
            confidences = snapshot.get("source_confidence") or {"_": 0.0}
            item.events.append(
                TimelinePromoter._event(
                    "state_snapshot", item.round_no, second, actor="system",
                    confidence=min(confidences.values()),
                    attributes={
                        "fields": sorted(k for k in confidences),
                        "producer": PRODUCER,
                        "promotion_rule": "knowledge_reader_values_in_observed_self_alive_second",
                    },
                    evidence_refs=refs.get(second, ()),
                )
            )
            have.add(second)

    # -- kill feed -----------------------------------------------------------------------

    def _recover_deaths(
        self, view: TimelineView, by_second: Mapping[int, Observation],
        item: RoundPromotion, report: SecondFeatureReport, stats: dict[str, Any],
    ) -> None:
        """A recorder death the spectator rule could not promote, from the timeline's
        own view ending plus one top-bar ally drop.

        When the recorder is the last ally alive the Round ends at once (no spectator
        view), and after some deaths the spectator view appears only seconds later.
        Promoted only if: the timeline never observes the own live view again in the
        Round after its last observed own live second L; exactly one ally drop of the
        top bar falls in [L - 1, L + death_drop_after_sec + 1]; and the drop is backed
        by an observed spectator view after L or by the ally count reaching 0. The
        Round must have no promoted death yet.
        """
        assert item.start is not None and item.end is not None and item.window is not None
        if any(e["type"] == "player_death" for e in item.events):
            return
        live = [
            row.index for row in view.seconds[item.start.time_sec:item.end.time_sec]
            if self._own_live(row)
        ]
        if not live:
            return
        last = live[-1]
        window = range(last - 1, last + self.policy.death_drop_after_sec + 2)
        drops: list[tuple[int, int]] = []  # (second the lower count is read, new count)
        previous: tuple[int, int] | None = None
        for second in range(max(item.start.time_sec, last - 6), item.end.time_sec + 1):
            pair = _bar_pair(by_second.get(second))
            if pair is None or _bar_pair(by_second.get(second + 1)) != pair:
                continue
            if previous is not None and pair[0] < previous[0] and second in window:
                drops.append((second, pair[0]))
            previous = pair
        if not drops:
            return
        if len(drops) != 1:
            report.rejected["recovered_death_ambiguous_ally_drops"] += 1
            return
        second, remaining = drops[0]
        spectated = any(
            (row.camera_value, row.camera_status) == ("SPECTATOR", _OBSERVED)
            for row in view.seconds[last + 1:item.end.time_sec + 1]
        )
        if not spectated and remaining != 0:
            report.rejected["recovered_death_not_backed"] += 1
            return
        last_row = view.row(last)
        refs = tuple(dict.fromkeys(
            [*(last_row.evidence_refs if last_row is not None else ()),
             *((self._refs[second],) if second in self._refs else ())]
        ))
        event = TimelinePromoter._event(
            "player_death", item.round_no, second, actor="player",
            confidence=self.policy.recovered_death_confidence,
            attributes={
                "last_self_alive_sec": last,
                "promotion_rule": (
                    "own_view_end_with_single_top_bar_ally_drop"
                    + ("_and_spectator" if spectated else "_team_eliminated")
                ),
                "producer": PRODUCER,
                "evidence_provenance": {"elimination_coverage": "self_death_only"},
            },
            evidence_refs=refs,
        )
        item.events.append(event)
        self.contract.validate_event(event, "hud_analyzer")
        report.counts["recovered_deaths"] += 1
        stats["recovered_death"] = second

    def _eliminations(
        self, view: TimelineView, by_second: Mapping[int, Observation],
        feed_new: Sequence[FeedArrival], item: RoundPromotion,
        report: SecondFeatureReport, stats: dict[str, Any],
    ) -> None:
        """Elimination order from the top-bar alive counts (#153 top_bar reader).

        The top bar is visible in the own view and while spectating, so every
        elimination of the Round shows up as a drop of one team's count. Each drop
        becomes a ``kill`` Event at the first second the lower count is read; the
        recorder's own death (the timeline's ``player_death``) takes the ally drop it
        matches. The kill feed is used only to name the recorder as the killer.
        """
        assert item.start is not None and item.end is not None
        combat = list(range(item.start.time_sec, item.end.time_sec + 1))
        stable: dict[int, tuple[int, int]] = {}
        for second in combat:
            pair = _bar_pair(by_second.get(second))
            if pair is not None and any(
                _bar_pair(by_second.get(second + d)) == pair for d in (-1, 1)
            ):
                stable[second] = pair
        coverage = len(stable) / max(1, len(combat))
        stats["top_bar_coverage"] = round(coverage, 3)
        if coverage < self.policy.top_bar_min_coverage:
            report.rejected["top_bar_coverage_too_low"] += 1
            return
        seconds = sorted(stable)
        opening = [s for s in seconds if s - item.start.time_sec <= 10]
        if not opening or stable[opening[0]] != (5, 5):
            report.rejected["top_bar_not_full_at_start"] += 1
            return
        # Drops: (lower bracket second, upper second, team, count).
        drops: list[tuple[int, int, str, int]] = []
        previous, previous_at = (5, 5), opening[0]
        for second in seconds:
            pair = stable[second]
            if pair == previous:
                previous_at = second
                continue
            if pair[0] > previous[0] or pair[1] > previous[1]:
                held = all(
                    stable.get(second + d) == pair
                    for d in range(self.policy.alive_increase_hold_sec)
                )
                if not held:
                    report.rejected["top_bar_increase_unconfirmed"] += 1
                    continue
                report.counts["top_bar_revives"] += 1
            for team, slot in (("ally", 0), ("enemy", 1)):
                if pair[slot] < previous[slot]:
                    drops.append((previous_at, second, team, previous[slot] - pair[slot]))
            previous, previous_at = pair, second
        units = [
            (index, number) for index, drop in enumerate(drops) for number in range(drop[3])
        ]
        assigned, highlighted = self._assign_feed(feed_new, drops, units, item, report, stats)

        def unit_sec(unit: tuple[int, int]) -> float | None:
            arrival = assigned.get(unit)
            return None if arrival is None else feed_new[arrival].sec

        def resolved(unit: tuple[int, int], others: Sequence[tuple[int, int]]) -> bool:
            # The feed orders two eliminations read in the same top-bar interval only
            # when both entries were assigned and first appeared in different reads.
            mine = unit_sec(unit)
            return mine is not None and all(
                (theirs := unit_sec(other)) is not None and theirs != mine for other in others
            )

        def overlapping(index: int) -> list[tuple[int, int]]:
            low, high = drops[index][0], drops[index][1]
            return [
                unit for unit in units
                if unit[0] != index and drops[unit[0]][0] < high and low < drops[unit[0]][1]
            ]

        deaths = [e for e in item.events if e["type"] == "player_death"]
        claimed: dict[tuple[int, int], dict[str, Any]] = {}
        complete = True
        for death in deaths:
            when = int(death["time_sec"])
            free = [unit for unit in units if unit not in claimed and drops[unit[0]][2] == "ally"]
            near = [
                unit for unit in free
                if when - self.policy.death_drop_before_sec <= drops[unit[0]][1]
                and drops[unit[0]][0] <= when + self.policy.death_drop_after_sec
            ]
            # The spectator view starts after the death camera, a few seconds after
            # the elimination: a drop the feed names as the recorder's may lie up to
            # death_feed_lookback_sec earlier, if the timeline never observes the
            # recorder's own live view after it.
            named = [
                unit for unit in free
                if unit in highlighted and feed_new[highlighted[unit]].recorder_victim
                and when - self.policy.death_feed_lookback_sec <= drops[unit[0]][1]
                and drops[unit[0]][0] <= when + self.policy.death_drop_after_sec
                and not any(
                    self._own_live(view.row(s))
                    for s in range(drops[unit[0]][1] + 1, when)
                )
            ]
            named_anywhere = [
                unit for unit in free
                if unit in highlighted and feed_new[highlighted[unit]].recorder_victim
            ]
            death["attributes"]["kill_feed_attribution"] = (
                "recorder_victim" if named else "none_assigned"
            )
            if len(named) == 1:
                unit = named[0]
            elif named:
                report.rejected["death_feed_ambiguous"] += 1
                complete = False
                continue
            elif named_anywhere:
                # The feed names the recorder as victim at another drop than the one
                # the timeline death is near: the attribution conflicts.
                death["attributes"]["kill_feed_attribution"] = "conflict"
                report.rejected["death_feed_attribution_conflict"] += 1
                complete = False
                continue
            elif len({u[0] for u in near}) == 1 and drops[near[0][0]][3] == 1:
                unit = near[0]
            else:
                report.rejected[
                    "death_top_bar_unmatched" if not near else "death_top_bar_ambiguous"
                ] += 1
                complete = False
                continue
            index = unit[0]
            low, high, _, count = drops[index]
            same_drop = [u for u in units if u[0] == index and u != unit]
            others = overlapping(index) + same_drop
            earlier = [d for d in drops[:index] if d[1] <= low]
            if others and not resolved(unit, others):
                report.rejected["death_top_bar_order_ambiguous"] += 1
                complete = False
                continue
            if count > 1 and not earlier and not resolved(unit, same_drop):
                report.rejected["death_top_bar_order_ambiguous"] += 1
                complete = False
                continue
            claimed[unit] = death
            provenance = death["attributes"]["evidence_provenance"]
            provenance["elimination_coverage"] = "top_bar_alive_counts"
            provenance["elimination_sec"] = high
            if (feed_sec := unit_sec(unit)) is not None:
                provenance["feed_sec"] = feed_sec
            refs = provenance["evidence_refs"]
            for ref in (self._refs.get(high), self._feed_refs.get(assigned.get(unit, -1))):
                if ref and ref not in refs:
                    refs.append(ref)
            death["attributes"]["top_bar_coverage"] = stats["top_bar_coverage"]
            report.counts["deaths_with_elimination_order"] += 1
        coverage_kind = "top_bar_alive_counts" if complete else "top_bar_partial"
        if not complete:
            # A recorder death without its drop: the Round's elimination list is not
            # known to be complete, so no first-elimination fact may be derived.
            report.rejected["round_elimination_order_incomplete"] += 1
        for unit in units:
            if unit in claimed:
                continue
            index, number = unit
            low, high, team, count = drops[index]
            others = overlapping(index)
            ambiguous = bool(others) and not resolved(unit, others)
            arrival = assigned.get(unit)
            entry = None if arrival is None else feed_new[arrival]
            mark = highlighted.get(unit)
            actor = "enemy" if team == "ally" else "unknown"
            if (
                team == "enemy" and mark is not None and feed_new[mark].recorder_killer
                and self._recorder_live(view, low, high)
            ):
                actor = "player"
            attributes: dict[str, Any] = {
                "victim_team": team,
                "drop_bracket_sec": [low, high],
                "order_ambiguous": ambiguous,
                "producer": PRODUCER,
                "promotion_rule": "top_bar_alive_count_drop_in_confirmed_combat",
                "evidence_provenance": {"elimination_coverage": coverage_kind},
            }
            if entry is not None:
                attributes["feed_sec"] = entry.sec
                attributes["kill_feed_killer_team"] = entry.killer_team
            feed_ref = None if arrival is None else self._feed_refs.get(arrival)
            refs = tuple(dict.fromkeys(
                ref for ref in (self._refs.get(high), feed_ref) if ref
            ))
            event = TimelinePromoter._event(
                "kill", item.round_no, high, actor=actor,
                confidence=self.policy.kill_confidence,
                attributes=attributes,
                evidence_refs=refs,
            )
            event["event_id"] = f"{event['event_id']}-{team}-{index}-{number}"
            item.events.append(event)
            report.counts["kill_events"] += 1
            if actor == "player":
                report.counts["kills_by_recorder"] += 1
        stats["kill_events"] = sum(1 for e in item.events if e["type"] == "kill")
        stats["top_bar_drops"] = len(drops)
        stats["top_bar_eliminations"] = len(units)
        stats["ally_eliminations"] = sum(1 for unit in units if drops[unit[0]][2] == "ally")
        stats["elimination_order_complete"] = complete

    def _assign_feed(
        self, feed_new: Sequence[FeedArrival], drops: Sequence[tuple[int, int, str, int]],
        units: Sequence[tuple[int, int]], item: RoundPromotion,
        report: SecondFeatureReport, stats: dict[str, Any],
    ) -> tuple[dict[tuple[int, int], int], dict[tuple[int, int], int]]:
        """Assign each new kill-feed entry to at most one top-bar elimination.

        Eliminations are taken in time order and each takes the earliest unused
        entry whose victim team is the dropping team, within the feed delay of the
        drop interval. Highlight arrivals (the recorder as victim or as killer) are
        assigned the same way in their own pass. Entries left over are phantom
        reads and name nobody. Returns (elimination entry, highlight entry) per
        elimination.
        """
        assert item.start is not None and item.end is not None
        window = self.policy.feed_match_window_sec
        in_round = [
            i for i, arrival in enumerate(feed_new)
            if item.start.time_sec <= arrival.sec <= item.end.time_sec + window
        ]
        ordered = sorted(units, key=lambda u: (drops[u[0]][1], drops[u[0]][0], u))
        used: set[int] = set()

        def assign(kind: str) -> dict[tuple[int, int], int]:
            out: dict[tuple[int, int], int] = {}
            for unit in ordered:
                low, high, team, _ = drops[unit[0]]
                for i in in_round:
                    arrival = feed_new[i]
                    if (
                        i not in used and arrival.kind == kind
                        and arrival.victim_team == team
                        and low - window <= arrival.sec <= high + window
                    ):
                        out[unit] = i
                        used.add(i)
                        break
            return out

        assigned = assign("elimination")
        highlighted = assign("highlight")
        inside = [i for i in in_round if feed_new[i].sec <= item.end.time_sec]
        phantom = [i for i in inside if i not in used]
        eliminations = [i for i in inside if feed_new[i].kind == "elimination"]
        stats["feed_new_entries"] = len(eliminations) + sum(
            1 for i in assigned.values() if feed_new[i].sec > item.end.time_sec
        )
        stats["feed_assigned"] = len(assigned)
        stats["feed_phantom"] = len(phantom)
        report.counts["feed_assigned"] += len(assigned)
        report.counts["feed_highlights_assigned"] += len(highlighted)
        report.counts["feed_phantom"] += len(phantom)
        report.counts["eliminations_without_feed"] += len(units) - len(assigned)
        return assigned, highlighted

    def _recorder_live(self, view: TimelineView, low: int, high: int) -> bool:
        return any(self._own_live(view.row(s)) for s in range(max(0, low - 3), high + 1))

    # -- economy ---------------------------------------------------------------------------

    def _score_before(
        self, by_second: Mapping[int, Observation], item: RoundPromotion,
        previous_end: int | None,
    ) -> tuple[tuple[int, int], tuple[str, ...]] | None:
        """Top-bar score shown before the Round's result, by stable-read majority.

        The score changes only with a Round's result, so every read from the end of
        the previous confirmed Round (or this Round's buy phase) to just before this
        Round's end shows the score before it. Only reads repeated in the next
        second and adding up to the Round number minus one (the timeline's Round
        number) are votes; the winner needs ``score_min_reads`` votes and
        ``score_min_share`` of them.
        """
        assert item.window is not None and item.end is not None
        votes: Counter[tuple[int, int]] = Counter()
        seconds: dict[tuple[int, int], list[int]] = {}
        first = item.window[0] if previous_end is None else min(item.window[0], previous_end + 2)
        for second in range(first, item.end.time_sec - 1):
            obs, following = by_second.get(second), by_second.get(second + 1)
            score = None if obs is None else obs.score
            if (
                score is None or following is None or following.score != score
                or not all(isinstance(v, int) and not isinstance(v, bool) for v in score)
            ):
                continue
            pair = (int(score[0]), int(score[1]))  # type: ignore[arg-type]
            if sum(pair) != item.round_no - 1:
                continue
            votes[pair] += 1
            seconds.setdefault(pair, []).append(second)
        if not votes:
            return None
        pair, count = votes.most_common(1)[0]
        if (
            count < self.policy.score_min_reads
            or count / sum(votes.values()) < self.policy.score_min_share
        ):
            return None
        refs = tuple(dict.fromkeys(self._refs[s] for s in seconds[pair] if s in self._refs))
        return pair, refs[:3]

    def _enemy_economy(
        self, by_second: Mapping[int, Observation], result: PromotionResult,
        report: SecondFeatureReport,
    ) -> None:
        """``enemy_eco_likely`` from the score chain and the game's credit rules.

        After the half's first Round, every player started that half with
        ``credits_half_start``. If the recorder's team won it, each enemy can carry
        at most the half-start credits, the first loss bonus, the spike-plant bonus
        and the kill rewards of that Round (no spending assumed). When even that
        upper bound of the enemy's average credits is below the cheapest full buy
        (highest rifle cost plus heavy shield), the enemy cannot full-buy and the
        Round gets ``enemy_eco_likely = True``. Nothing proves the opposite (saved
        weapons, uneven credits), so ``False`` is never produced.
        """
        knowledge = self.knowledge
        per_half = int(knowledge.rule("regulation_rounds_per_half"))
        team = int(knowledge.rule("team_size"))
        full_buy = max(
            w.cost for w in knowledge.weapons if w.category == "Rifle" and w.cost
        ) + int(knowledge.rule("heavy_shield_cost"))
        confirmed = {item.round_no: item for item in result.rounds if item.confirmed}
        scores: dict[int, tuple[tuple[int, int], tuple[str, ...]]] = {}
        for number, item in confirmed.items():
            before = confirmed.get(number - 1)
            previous_end = None if before is None or before.end is None else before.end.time_sec
            read = self._score_before(by_second, item, previous_end)
            # The shared timeline's own score consensus (#164 round_meta) comes first;
            # the top-bar reader fills Rounds without it and must not contradict it.
            timeline = item.round_meta.get("score_before")
            if isinstance(timeline, dict) and None not in (
                timeline.get("ally"), timeline.get("enemy")
            ):
                pair = (int(timeline["ally"]), int(timeline["enemy"]))
                if read is not None and read[0] != pair:
                    report.rejected["score_timeline_reader_conflict"] += 1
                    continue
                if read is not None:
                    report.counts["score_timeline_reader_agree"] += 1
                scores[number] = (pair, read[1] if read is not None else ())
            elif read is not None:
                scores[number] = read
        report.counts["rounds_with_score"] = len(scores)
        for number, item in sorted(confirmed.items()):
            half_first = number - 1
            if half_first not in {1, per_half + 1} or number not in scores:
                continue
            (ally, enemy), refs = scores[number]
            previous = scores.get(half_first)
            won = (ally, enemy) == (1, 0) if half_first == 1 else (
                previous is not None and (ally, enemy) == (
                    previous[0][0] + 1, previous[0][1]
                )
            ) or (
                half_first in confirmed
                and confirmed[half_first].round_meta.get("round_result") == "win"
                and ally + enemy == per_half + 1
            )
            if not won:
                report.counts["economy_rounds_not_after_won_pistol"] += 1
                continue
            stats = report.per_round.get(half_first, {})
            kills = stats.get("ally_eliminations")
            if not isinstance(kills, int) or not stats.get("elimination_order_complete"):
                kills = 2 * team  # unread: a generous bound (revives included)
            bound = (
                int(knowledge.rule("credits_half_start"))
                + int(knowledge.rule("round_loss_credits")[0])
                + int(knowledge.rule("spike_plant_credits"))
                + int(knowledge.rule("kill_credits")) * kills / team
            )
            bound = min(bound, float(knowledge.rule("credits_cap")))
            if bound >= full_buy:
                report.counts["economy_bound_not_below_full_buy"] += 1
                continue
            target = next(
                (e for e in item.events if e["type"] == "buy_phase"),
                next((e for e in item.events if e["type"] == "round_start"), None),
            )
            if target is None:
                report.rejected["enemy_eco_no_round_event"] += 1
                continue
            target["attributes"]["enemy_economy"] = {
                "enemy_eco_likely": True,
                "confidence": self.policy.enemy_eco_confidence,
                "enemy_average_credits_upper_bound": round(bound),
                "full_buy_min_cost": full_buy,
                "score_before": [ally, enemy],
                "after_won_round": half_first,
                "ally_eliminations_used": kills,
                "rule_source": "community_economy_references",
                "evidence_refs": list(refs),
            }
            report.counts["enemy_eco_rounds"] += 1
            report.per_round.setdefault(number, {})["enemy_eco_likely"] = True

    # -- revive and DOWNED ----------------------------------------------------------------

    def _revives_and_downed(
        self, view: TimelineView, item: RoundPromotion, report: SecondFeatureReport,
        stats: dict[str, Any],
    ) -> None:
        assert item.window is not None and item.end is not None
        downed = sum(1 for row in view.seconds[item.window[0]:item.window[1]]
                     if row.life_value == "DOWNED")
        report.counts["downed_seconds"] += downed
        stats["downed_seconds"] = downed
        for death in (e for e in item.events if e["type"] == "player_death"):
            second = int(death["time_sec"])
            run = best = 0
            revived_at: int | None = None
            for row in view.seconds[second + 1:item.end.time_sec]:
                run = run + 1 if self._own_live(row) else 0
                if run > best:
                    best = run
                if run >= self.policy.revive_min_live_sec and revived_at is None:
                    revived_at = row.index - run + 1
            if revived_at is not None:
                death["attributes"]["revived_at_sec"] = revived_at
                report.counts["revives"] += 1
        stats["revives"] = sum(
            1 for e in item.events
            if e["type"] == "player_death" and "revived_at_sec" in e["attributes"]
        )


def _event_order(event: Mapping[str, Any]) -> tuple[float, float, int]:
    """Time order; a death matched to a top-bar drop sits at that drop's second, so
    FactBuilder reads the elimination order from the list order. Within one second
    an elimination with an assigned kill-feed entry is ordered by that entry."""
    attributes = event.get("attributes") or {}
    provenance = attributes.get("evidence_provenance") or {}
    when = float(provenance.get("elimination_sec", event["time_sec"]))
    feed = provenance.get("feed_sec", attributes.get("feed_sec"))
    rank = {"round_start": 0, "buy_phase": 1, "player_death": 2, "kill": 3}.get(
        str(event["type"]), 4 if event["type"] != "round_end" else 9
    )
    return when, float(feed) if feed is not None else math.inf, rank


def _first_elimination(death: Mapping[str, Any], kills: Sequence[Mapping[str, Any]]) -> bool:
    """Whether the death precedes every kill Event in the promoted order."""
    mine = _event_order(death)
    return not any(_event_order(kill) < mine for kill in kills)


def _bar_pair(obs: Observation | None) -> tuple[int, int] | None:
    """Top-bar alive counts as read (both teams 0..5), or None."""
    if obs is None:
        return None
    ally, enemy = obs.ally_alive, obs.enemy_alive
    if (
        isinstance(ally, int) and isinstance(enemy, int)
        and not isinstance(ally, bool) and not isinstance(enemy, bool)
        and 0 <= ally <= 5 and 0 <= enemy <= 5
    ):
        return ally, enemy
    return None


def _alive_pair(obs: Observation | None) -> tuple[int, int] | None:
    if obs is None:
        return None
    ally, enemy = obs.ally_alive, obs.enemy_alive
    if (
        isinstance(ally, int) and isinstance(enemy, int)
        and not isinstance(ally, bool) and not isinstance(enemy, bool)
        and 1 <= ally <= 5 and 0 <= enemy <= 5
    ):
        return ally, enemy
    return None


def _utility_count(obs: Observation) -> int:
    return sum(1 for value in obs.charges[:3] if float(value) >= _CHARGE_AVAILABLE)


def _empty_snapshot(second: int) -> dict[str, Any]:
    return {
        "time_sec": float(second),
        "ally_alive": None,
        "enemy_alive": None,
        "hp": None,
        "armor": None,
        "weapon": None,
        "spike_state": "unknown",
        "round_time_remaining_sec": None,
        "utility_available_count": None,
        "player_location": {"zone_id": None, "zone_name": None},
        "known_enemy_locations": [],
        "spatial_context": {
            "cover_available": None,
            "escape_route_available": None,
            "line_of_sight_state": "unknown",
            "exposed_directions_count": None,
            "view_target_zone_id": None,
        },
        "score_ally": None,
        "score_enemy": None,
        "source_confidence": {},
    }


__all__ = [
    "FORMAL_QUALIFICATION",
    "PRODUCER",
    "SecondFeaturePolicy",
    "SecondFeaturePromoter",
    "SecondFeatureReport",
    "load_records",
    "records_source_sha256",
]
