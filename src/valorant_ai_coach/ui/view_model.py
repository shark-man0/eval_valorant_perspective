"""Qt-free presentation logic for evaluation results.

Everything here is a pure function of the stored evaluations: the UI never edits a label,
confidence or timestamp, and never invents a clip or an evidence range that is not stored.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from .contracts import EvaluationView

SCORED_LABELS = frozenset({"good", "improve"})
_LABELS = ("good", "improve", "unscored")


def label_counts(evaluations: Iterable[EvaluationView]) -> dict[str, int]:
    """Counts per label. Every evaluation falls in exactly one of the three labels."""
    counts = dict.fromkeys(_LABELS, 0)
    for evaluation in evaluations:
        counts[evaluation.label] += 1
    return counts


def filter_evaluations(
    evaluations: Sequence[EvaluationView],
    *,
    label: str = "scored",
    category: str = "all",
    round_no: int = -1,
) -> list[EvaluationView]:
    """Select evaluations to show.

    label: ``scored`` (good + improve), ``good``, ``improve``, ``unscored``,
    ``review`` (scored but low confidence) or ``all``. Any other value matches nothing.
    """
    selected: list[EvaluationView] = []
    for evaluation in evaluations:
        if label == "scored" and evaluation.label not in SCORED_LABELS:
            continue
        if label == "review" and not evaluation.needs_review:
            continue
        if label not in {"all", "scored", "review"} and evaluation.label != label:
            continue
        if category != "all" and evaluation.category != category:
            continue
        if round_no != -1 and evaluation.round_no != round_no:
            continue
        selected.append(evaluation)
    return selected


def format_clock(seconds: float) -> str:
    minutes, remainder = divmod(max(0, round(seconds)), 60)
    return f"{minutes:02d}:{remainder:02d}"


def parse_time_range(value: object) -> tuple[float, float] | None:
    """The stored evidence range as (start, end), or None if absent or unusable."""
    if not isinstance(value, dict):
        return None
    start, end = value.get("start_sec"), value.get("end_sec")
    for item in (start, end):
        if isinstance(item, bool) or not isinstance(item, int | float) or not math.isfinite(item):
            return None
    assert isinstance(start, int | float) and isinstance(end, int | float)
    return (float(start), float(end)) if end >= start else None


def time_range_text(time_range: tuple[float, float] | None) -> str | None:
    if time_range is None:
        return None
    start, end = time_range
    return f"{format_clock(start)}–{format_clock(end)}（{start:.1f}–{end:.1f}秒）"


def clip_status(evaluation: EvaluationView) -> str:
    if evaluation.clip_path:
        return "クリップあり"
    if evaluation.label == "unscored":
        return "クリップなし（評価対象外のため生成されません）"
    return "クリップなし"


__all__ = [
    "SCORED_LABELS",
    "clip_status",
    "filter_evaluations",
    "format_clock",
    "label_counts",
    "parse_time_range",
    "time_range_text",
]
