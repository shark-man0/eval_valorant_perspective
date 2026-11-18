"""Per-second observations (from ``extract_second_features.py``) for the rule
producers, plus shot, movement and peek candidates (development only).

Shots: the magazine count only drops when the viewed player fires, so a drop
between two consecutive one-second readings in the recorder's own live view is
a shot event in that second (count = size of the drop). A rise is a reload or a
weapon switch, never a shot. A drop larger than a magazine empties in one
second for any weapon is treated as a misread. When the reserve count is read
at both ends and differs, the weapon changed (a switch), so the drop is not a
shot. Readings are paired only inside one round of the shared timeline
(``segments``), only while the view stays the recorder's own and only across
short unreadable gaps, so no event spans a round boundary, spectating or a
missing interval.

Movement: between a keyframe and the frame 2/60 s later, a pure camera rotation
moves every playfield point by one homography; walking adds parallax that the
homography cannot explain. ``MOVING_RESIDUAL_PX`` on that residual (480x270
scale) is the best split on reviewed TRAIN seconds, but it is right only 4 of 9
times it says "moving" (recall 4/5), so movement, peeks and the facts that
need movement are gated off (``include_movement=False``) and do not reach the
rules until a better detector passes review.

Peek: a stationary -> moving onset followed by the recorder's shot within
``PEEK_TO_SHOT_SEC``; a moving -> stationary stop shortly after an onset with
no shot is an ``info_peek`` candidate.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .development_readiness import FeedKill, Observation

SWITCH_MIN_DROP = 3
MOVING_RESIDUAL_PX = 3.0
MIN_TRACKED = 30
PEEK_TO_SHOT_SEC = 2.0
MAX_READ_GAP_SEC = 3.5  # magazine readings further apart are not compared
INFO_PEEK_MAX_SEC = 3.0
VICTIM_MIN_SCORE = 0.6


@dataclass(frozen=True)
class SecondRecord:
    observation: Observation
    magazine: int | None
    residual_p90: float | None
    tracked: int
    reserve: int | None = None


def _motion(record: dict[str, Any]) -> tuple[float | None, int]:
    motion = record.get("motion") or []
    later = motion[-1] if motion else {}
    tracked = int(later.get("tracked", 0))
    residual = later.get("residual_p90")
    return (float(residual) if residual is not None and tracked >= MIN_TRACKED else None,
            tracked)


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def load_second_records(path: Path, ammo_path: Path | None = None) -> list[SecondRecord]:
    """Rows of ``extract_second_features.py``; ``ammo_path`` (``--ammo-only`` rows)
    adds the reserve count to rows written before it was read. Rows are matched
    by native sample identity (PTS tick and encoded-packet SHA-256)."""
    rows = _rows(path)
    rows.sort(key=lambda r: r["sec"])
    reserve: dict[tuple[int, str], int | None] = {}
    if ammo_path is not None and ammo_path.exists():
        for extra in _rows(ammo_path):
            sample = extra["sample"]
            reserve[(int(sample["native_pts_tick"]), sample["acquired_frame_sha256"])] = \
                extra.get("reserve")
    out = []
    for row in rows:
        hud = row.get("hud") or {}
        alive = row.get("alive") or [None, None]
        score = row.get("score") or [None, None]
        feed = tuple(
            FeedKill(e["killer_team"], e["victim_team"],
                     e["victim"] if e.get("victim_score", 0) >= VICTIM_MIN_SCORE else None,
                     bool(e["recorder_killer"]), bool(e["recorder_victim"]))
            for e in row.get("feed") or [])
        observation = Observation(
            float(row["sec"]), bool(hud.get("present")), hud.get("agent"),
            float(hud.get("agent_score", 0.0)), tuple(hud.get("charges") or (0, 0, 0, 0)),
            alive[0], alive[1], row.get("planted"), feed,
            spike_carried=row.get("spike_carried"), spike_score=row.get("spike_score"),
            score=(score[0], score[1]), timer=row.get("timer"))
        residual, tracked = _motion(row)
        sample = row.get("sample") or {}
        key = (int(sample.get("native_pts_tick", -1)), str(sample.get("acquired_frame_sha256")))
        out.append(SecondRecord(observation, row.get("magazine"), residual, tracked,
                                row.get("reserve", reserve.get(key))))
    return out


@dataclass(frozen=True)
class Shot:
    sec: float
    count: int
    first: bool  # first shot after a pause (engagement start candidate)
    moving: bool | None


@dataclass(frozen=True)
class MovementChange:
    sec: float
    moving: bool


def moving_state(records: Sequence[SecondRecord]) -> list[bool | None]:
    return [None if r.residual_p90 is None else r.residual_p90 >= MOVING_RESIDUAL_PX
            for r in records]


@dataclass(frozen=True)
class WeaponLimits:
    """From the knowledge base: what a magazine drop can be."""

    max_fire_rate: float = 16.0  # shots per second, fastest weapon
    switch_magazines: frozenset[int] = frozenset()  # full sidearm magazines

    @classmethod
    def from_knowledge(cls, weapons: Iterable[Any]) -> WeaponLimits:
        rates = [w.fire_rate for w in weapons if w.fire_rate]
        sidearms = {int(w.magazine_size) for w in weapons
                    if w.category == "Sidearm" and w.magazine_size}
        return cls(max(rates) if rates else 16.0, frozenset(sidearms))


def _segments(records: Sequence[SecondRecord],
              segments: Sequence[int | None] | None) -> Sequence[int | None]:
    if segments is None:
        return [0] * len(records)
    if len(segments) != len(records):
        raise ValueError("one segment (round index) per record required")
    return segments


def _clock_restarted(before: SecondRecord, after: SecondRecord) -> bool:
    """The round clock went up: a new phase or round started in between."""
    early, late = before.observation.timer, after.observation.timer
    return early is not None and late is not None and late > early


def is_switch(before: SecondRecord, after: SecondRecord, limits: WeaponLimits) -> bool:
    """The weapon changed between two readings: the reserve count differs (when
    read at both ends), or a drop of more than a few rounds lands exactly on a
    full sidearm magazine (pulling out the pistol)."""
    if before.reserve is not None and after.reserve is not None \
            and before.reserve != after.reserve:
        return True
    assert before.magazine is not None and after.magazine is not None
    drop = before.magazine - after.magazine
    return drop > SWITCH_MIN_DROP and after.magazine in limits.switch_magazines


def detect_shots(records: Sequence[SecondRecord], own_live: Sequence[bool],
                 *, pause_sec: float = 3.0, limits: WeaponLimits | None = None,
                 segments: Sequence[int | None] | None = None) -> list[Shot]:
    """Shots from magazine drops between consecutive readings in own live view.

    Unreadable seconds in between are skipped (up to ``MAX_READ_GAP_SEC``), so a
    drop across a gap is one shot event at the later reading; the view must
    stay the recorder's own the whole time and both readings must lie in the
    same round (``segments``: the shared timeline's round index per record, or
    ``None`` where it has none) with no clock restart in between. A drop faster than the
    fastest weapon can fire is a misread; a weapon switch (``is_switch``) is not
    a shot. The first shot of a round, or after ``pause_sec`` without one, is an
    engagement start candidate.
    """
    limits = limits or WeaponLimits()
    moving = moving_state(records)
    rounds = _segments(records, segments)
    shots: list[Shot] = []
    shot_round: int | None = None
    last: int | None = None  # index of the previous magazine reading in own view
    for index, record in enumerate(records):
        if not own_live[index]:
            last = None
            continue
        if last is not None and (rounds[last] != rounds[index]
                                 or _clock_restarted(records[last], record)):
            last = None
        if record.magazine is None:
            continue
        if last is not None and record.observation.sec - records[last].observation.sec \
                <= MAX_READ_GAP_SEC:
            previous = records[last]
            assert previous.magazine is not None
            drop = previous.magazine - record.magazine
            elapsed = record.observation.sec - previous.observation.sec
            if 0 < drop <= limits.max_fire_rate * elapsed + 1 \
                    and not is_switch(previous, record, limits):
                sec = record.observation.sec
                first = (not shots or shot_round != rounds[index]
                         or sec - shots[-1].sec > pause_sec)
                shots.append(Shot(sec, drop, first, moving[last]))
                shot_round = rounds[index]
        last = index
    return shots


def movement_changes(records: Sequence[SecondRecord], own_live: Sequence[bool],
                     segments: Sequence[int | None] | None = None) -> list[MovementChange]:
    changes: list[MovementChange] = []
    previous: bool | None = None
    previous_round: int | None = None
    rounds = _segments(records, segments)
    for record, state, live, round_index in zip(records, moving_state(records), own_live,
                                                rounds, strict=True):
        if not live or state is None or round_index != previous_round:
            previous = None
        previous_round = round_index
        if not live or state is None:
            continue
        if previous is not None and state != previous:
            changes.append(MovementChange(record.observation.sec, state))
        previous = state
    return changes


def peeks(changes: Iterable[MovementChange], shots: Sequence[Shot]
          ) -> tuple[list[float], list[float]]:
    """(peek, info_peek) candidate times."""
    changes = list(changes)
    shot_secs = [s.sec for s in shots]
    peek, info = [], []
    for index, change in enumerate(changes):
        if not change.moving:
            continue
        if any(change.sec <= t <= change.sec + PEEK_TO_SHOT_SEC for t in shot_secs):
            peek.append(change.sec)
            continue
        stop = next((c for c in changes[index + 1:] if not c.moving), None)
        if (stop is not None and stop.sec - change.sec <= INFO_PEEK_MAX_SEC
                and not any(change.sec <= t <= stop.sec + 1 for t in shot_secs)):
            info.append(change.sec)
    return peek, info


def second_additions(records: Sequence[SecondRecord], own_live: Sequence[bool],
                     limits: WeaponLimits | None = None, *, include_movement: bool = False,
                     segments: Sequence[int | None] | None = None,
                     ) -> dict[float, tuple[set[str], dict[str, Any]]]:
    """Candidate events/facts per second for shots (and, when enabled, movement
    and peeks)."""
    out: dict[float, tuple[set[str], dict[str, Any]]] = {}

    def at(sec: float) -> tuple[set[str], dict[str, Any]]:
        return out.setdefault(sec, (set(), {}))

    shots = detect_shots(records, own_live, limits=limits, segments=segments)
    for shot in shots:
        events, facts = at(shot.sec)
        events.add("shot")
        facts["first_shot_detected"] = shot.first
        if shot.first:
            events.add("engagement_start")
        if include_movement and shot.moving is not None:
            facts["shot_while_moving"] = shot.moving
            if shot.first:
                facts["first_shot_stationary"] = not shot.moving
    if not include_movement:
        return out
    changes = movement_changes(records, own_live, segments)
    for change in changes:
        at(change.sec)[0].add("movement_state")
    peek, info = peeks(changes, shots)
    for sec in peek:
        at(sec)[0].add("peek")
    for sec in info:
        at(sec)[0].add("info_peek")
    return out
