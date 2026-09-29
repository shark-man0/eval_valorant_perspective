"""Bounded, one-to-one joins of HUD evidence on the recording's time axis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .temporal import resolve_kill_sides


def join_hud_timeline(
    observations: Sequence[dict[str, Any]],
    evidence_by_frame: Mapping[int, Mapping[str, Any]],
    *,
    round_window_sec: float = 3.0,
    kill_window_sec: float = 0.75,
) -> dict[int, dict[str, Any]]:
    """Join both orderings without recycling one roster drop for multiple rows.

    Mutates only canonical observation flags/anonymous feed rows; internal
    provenance stays in the separate evidence map, never in the JSON Schema.
    """
    evidence = {
        int(item.get("frame_index", i)): dict(
            evidence_by_frame.get(int(item.get("frame_index", i)), {})
        )
        for i, item in enumerate(observations)
    }
    times = [float(item["time_sec"]) for item in observations]
    keys = [int(item.get("frame_index", i)) for i, item in enumerate(observations)]
    values = [item.get("values", {}) for item in observations]
    confidences = [float(item.get("quality", {}).get("hud_confidence", 0)) for item in observations]
    score_changes: list[int] = []
    drops: list[tuple[int, int]] = []
    rows: list[tuple[int, int]] = []
    previous_roster: int | None = None
    for i, value in enumerate(values):
        proof = evidence[keys[i]]
        proof["kill_timeline_managed"] = True
        proof.pop("kill_roster_pairs", None)
        if i and min(confidences[i - 1], confidences[i]) >= 0.65:
            before_score = (values[i - 1].get("score_ally"), values[i - 1].get("score_enemy"))
            after_score = (value.get("score_ally"), value.get("score_enemy"))
            if (
                all(type(number) is int for number in (*before_score, *after_score))
                and before_score != after_score
                and times[i] - times[i - 1] <= round_window_sec
            ):
                score_changes.append(i)
        if (
            all(type(value.get(f"{side}_alive")) is int for side in ("ally", "enemy"))
            and confidences[i] >= 0.65
        ):
            if previous_roster is not None and times[i] - times[previous_roster] <= max(
                1.0, kill_window_sec
            ):
                before = values[previous_roster]
                # Include ambiguous multi-death transitions too, so they block
                # an unsafe one-to-one assignment near another roster change.
                if any(
                    value[f"{side}_alive"] < before[f"{side}_alive"] for side in ("ally", "enemy")
                ):
                    drops.append((previous_roster, i))
            previous_roster = i
        added = proof.get("kill_feed_added_rows", proof.get("kill_feed_changed_rows", []))
        indices = list(added) if isinstance(added, (list, tuple)) else []
        if not indices and proof.get("kill_feed_row_added") is True:
            indices = [0]
        for row_index, row in enumerate(value.get("kill_feed_rows", [])):
            if row.get("row_added") is True:
                indices.append(row_index)
        rows.extend(
            (i, index) for index in sorted(set(indices)) if type(index) is int and index >= 0
        )

    # A score update corroborates its nearest banner, not every frame of a banner.
    banners = [
        i
        for i, item in enumerate(observations)
        if evidence[keys[i]].get("shared_banner")
        or evidence[keys[i]].get("round_end_template")
        or "round_end_banner" in item.get("state_flags", ())
    ]
    for i in range(len(observations)):
        evidence[keys[i]]["round_end_joined"] = False
    claimed_banners: set[int] = set()
    for change in score_changes:
        candidates = [
            i
            for i in banners
            if i not in claimed_banners
            and abs(times[i] - times[change]) <= round_window_sec
            and confidences[i] >= 0.65
            and not evidence[keys[i]].get("pre_round_context")
        ]
        if not candidates:
            continue
        chosen = min(candidates, key=lambda i: (abs(times[i] - times[change]), times[i]))
        claimed_banners.add(chosen)
        proof = evidence[keys[chosen]]
        proof.update(
            round_end_joined=True,
            round_end_score=(values[change].get("score_ally"), values[change].get("score_enemy")),
            round_end_join_confidence=min(
                confidences[chosen], confidences[change], confidences[change - 1]
            ),
        )
        flags = set(observations[chosen].get("state_flags", ()))
        flags.discard("buy_phase_banner")
        flags.add("round_end_banner")
        observations[chosen]["state_flags"] = sorted(flags)
        values[chosen]["buy_phase_visible"] = False

    nearby_drops = {
        row: [
            j
            for j, (_, end) in enumerate(drops)
            if abs(times[row[0]] - times[end]) <= kill_window_sec
        ]
        for row in rows
    }
    for row, candidates in nearby_drops.items():
        if len(candidates) != 1:
            continue
        drop = candidates[0]
        if sum(drop in choices for choices in nearby_drops.values()) != 1:
            continue
        before_index, after_index = drops[drop]
        before, after = values[before_index], values[after_index]
        assignment = resolve_kill_sides(
            kill_feed_row_added=True,
            ally_alive_before=before["ally_alive"],
            ally_alive_after=after["ally_alive"],
            enemy_alive_before=before["enemy_alive"],
            enemy_alive_after=after["enemy_alive"],
        )
        if assignment.victim_side == "unknown":
            continue
        index, row_index = row
        proof = evidence[keys[index]]
        pairs = proof.setdefault("kill_roster_pairs", {})
        pairs[row_index] = {
            "ally_before": before["ally_alive"],
            "ally_after": after["ally_alive"],
            "enemy_before": before["enemy_alive"],
            "enemy_after": after["enemy_alive"],
            "confidence": min(confidences[before_index], confidences[after_index]),
        }
        feed = values[index].setdefault("kill_feed_rows", [])
        while len(feed) <= row_index:
            feed.append({"raw_text": None, "confidence": 0.75})
        proof["kill_feed_added_rows"] = sorted(
            set(proof.get("kill_feed_added_rows", ())) | {row_index}
        )
    return evidence
