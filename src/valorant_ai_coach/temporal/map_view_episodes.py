"""Bound development Map portrait memory to recorded view episodes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from .evidence import digest, native_time, source_scope
from .map_recorder_camera import measure_recorder_view

_BOUNDARY_SIGNALS = {
    "death", "downed", "spectator", "remote", "result", "report",
    "round_start", "round_started", "revival",
}


@dataclass(frozen=True)
class ViewEpisode:
    episode_ref: str
    current_samples: tuple[str, ...]
    opening_boundary: str
    boundary_sample_ref: str | None
    observed_round_token: str | None


def _boundary(frame: dict[str, Any], signals: set[str]) -> str | None:
    if signals & {"death", "downed"}:
        return "observed_death_signal"
    if signals & {"spectator", "remote"}:
        return "observed_other_view"
    if frame["camera"]["value"] in {"SPECTATOR", "REMOTE"}:
        return "other_view_state"
    if frame["life"]["value"] in {"DEAD", "DOWNED"}:
        return "other_life_state"
    if frame["round"]["value"] in {"ENDED", "INTERMISSION"} or signals & {"result", "report"}:
        return "observed_round_end"
    if signals & {"round_start", "round_started"}:
        return "observed_round_start"
    if "revival" in signals:
        return "observed_revival"
    return None


def map_view_episodes(timeline: Mapping[str, Any]) -> tuple[ViewEpisode, ...]:
    """Use current SELF/ALIVE evidence with explicit time, view and lifecycle cuts.

    A short unknown view may lie between measured observations in the same
    episode. Only the measured samples are returned. A spectator boundary
    limits portrait reuse without assigning death to the recorder.
    """
    observations = timeline["observations"]
    frames = sorted(timeline["native_frames"].values(), key=lambda f: native_time(f["sample"]))
    result: list[ViewEpisode] = []
    current: list[str] = []
    opening = ("capture_start", None)
    previous: dict[str, Any] | None = None
    last_measured: Fraction | None = None
    supplier: str | None = None
    round_token: str | None = None

    def flush() -> None:
        nonlocal current, supplier, last_measured
        if current:
            result.append(ViewEpisode(
                digest(["map_view_episode_v1", current[0], opening, round_token]),
                tuple(current), opening[0], opening[1], round_token,
            ))
        current = []
        supplier = None
        last_measured = None

    for frame in frames:
        sample = frame["sample"]
        key = sample["sample_sha256"]
        at = native_time(sample)
        token = frame.get("round_token")
        rows = [observations[r] for r in frame["observation_ids"]]
        supplied, veto = measure_recorder_view(frame, rows)
        signals = {
            signal for r in rows
            if _BOUNDARY_SIGNALS.intersection(r.get("signals", ()))
            and r.get("sample") == sample
            and digest({k: v for k, v in r.items() if k != "observation_id"})
            == r.get("observation_id")
            for signal in r["signals"]
        }
        boundary = _boundary(frame, signals)
        if previous is not None:
            prior = previous["sample"]
            if (source_scope(prior) != source_scope(sample)
                    or not 0 < at - native_time(prior) <= Fraction(1, 4)
                    or frame.get("continuity", {}).get("carry_allowed") is not True
                    or frame.get("tracking_epoch") != previous.get("tracking_epoch")):
                flush()
                opening = ("capture_or_tracking_cut", key)
            elif token != previous.get("round_token"):
                flush()
                opening = ("round_scope_changed", key)
            elif previous["round"]["value"] == "BUY" and frame["round"]["value"] == "ACTIVE":
                flush()
                opening = ("observed_buy_to_active", key)
        previous = frame
        if boundary is not None or veto:
            flush()
            opening = (boundary or "current_view_veto", key)
            continue
        if last_measured is not None and (at - last_measured > Fraction(3, 4)
                        or supplied is not None and supplied != supplier):
            flush()
            opening = ("current_view_gap_or_change", key)
        if not (supplied and frame["camera"]["value"] == "SELF"
                and frame["life"]["value"] == "ALIVE"):
            continue
        if not current:
            round_token = token
        current.append(key)
        supplier = supplied
        last_measured = at
    flush()
    return tuple(result)
