"""Evidence conflict resolution before strict Round Package projection."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from valorant_ai_coach.events import EventSourceContract


class EvidenceFusion:
    def __init__(self, contract: EventSourceContract) -> None:
        self.contract = contract

    def events(
        self,
        hud: Sequence[dict[str, Any]],
        visual: Sequence[dict[str, Any]],
    ) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], tuple[str, ...]]:
        groups: list[list[tuple[str, dict[str, Any]]]] = []
        diagnostics: list[str] = []
        for source, events in (("hud_analyzer", hud), ("visual_analyzer", visual)):
            for event in events:
                self.contract.validate_event(event, source)  # type: ignore[arg-type]
                matching = next(
                    (
                        group
                        for group in groups
                        if group[0][1]["type"] == event["type"]
                        and group[0][1]["actor"] == event["actor"]
                        and abs(group[0][1]["time_sec"] - event["time_sec"]) <= 0.15
                        and group[0][0] != source
                    ),
                    None,
                )
                if matching is None:
                    groups.append([(source, event)])
                else:
                    matching.append((source, event))
        accepted: dict[str, list[dict[str, Any]]] = {"hud_analyzer": [], "visual_analyzer": []}
        for group in groups:
            kind = group[0][1]["type"]
            priority = self.contract.producer_for(kind)
            ranked = sorted(
                group,
                key=lambda pair: (float(pair[1]["confidence"]), pair[0] == priority),
                reverse=True,
            )
            source, winner = ranked[0]
            if len(ranked) > 1:
                runner = ranked[1][1]
                if (
                    winner["attributes"] != runner["attributes"]
                    and abs(winner["confidence"] - runner["confidence"]) < 0.05
                ):
                    diagnostics.append(f"fusion_conflict_unresolved:{kind}:{winner['time_sec']}")
                    continue
            accepted[source].append(dict(winner))
        return (
            tuple(accepted["hud_analyzer"]),
            tuple(accepted["visual_analyzer"]),
            tuple(diagnostics),
        )


def resolve_value(
    hud_value: Any, hud_confidence: float, visual_value: Any, visual_confidence: float
) -> Any:
    """Unknown is not a contradiction; close conflicting measurements abstain."""
    if visual_value is None or visual_confidence < 0.85:
        return hud_value
    if hud_value is None or hud_confidence < 0.65:
        return visual_value
    if hud_value == visual_value:
        return hud_value
    if abs(hud_confidence - visual_confidence) < 0.05:
        return None
    return visual_value if visual_confidence > hud_confidence else hud_value
