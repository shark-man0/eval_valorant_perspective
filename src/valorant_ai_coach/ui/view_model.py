"""Qt-free presentation logic for evaluation results.

Everything here is a pure function of the stored evaluations: the UI never edits a label,
confidence or timestamp, and never invents a clip or an evidence range that is not stored.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

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


def format_match_summary(
    value: Mapping[str, Any] | None, error: str | None = None
) -> str:
    """Compact read-only Match totals; full refs and context remain in JSON export."""
    if error:
        return "Match集計: 利用できません（保存データが不完全または不正）"
    if not value:
        return ""
    completeness = value.get("completeness") or {}
    rounds = value.get("rounds") or []
    rules = value.get("rules") or []
    refs = value.get("evaluations") or []
    counts = {label: sum(int(r["label_counts"][label]) for r in rounds
                         if r.get("status") == "included") for label in _LABELS}
    parts = [
        f"Match集計: {len(rounds)} Round / GOOD {counts['good']} / "
        f"IMPROVE {counts['improve']} / UNSCORED {counts['unscored']}",
        f"完全性: {completeness.get('status', 'unknown')} "
        f"(未評価 {len(completeness.get('rounds_not_evaluated', []))} / "
        f"除外 {len(completeness.get('rounds_excluded_invalid', []))})",
    ]
    if rules:
        entries = []
        for rule in rules[:8]:
            labels = rule.get("counts", {})
            entries.append(
                f"{rule['rule_id']} {labels.get('good', 0)}/"
                f"{labels.get('improve', 0)}/{labels.get('unscored', 0)}"
            )
        parts.append("Rule別 GOOD/IMPROVE/UNSCORED: " + "、".join(entries))
        if len(rules) > 8:
            parts.append(f"他 {len(rules) - 8} RuleはJSON参照")
    blockers = completeness.get("blocking_reasons") or []
    if blockers:
        parts.append("不完全の理由: " + ", ".join(str(x) for x in blockers[:8]))
    missing = sorted({
        str(item)
        for rule in rules
        for ctx in rule.get("context_by_round", [])
        for item in ctx.get("missing_context", [])
    })
    if missing:
        parts.append("不足文脈: " + ", ".join(missing[:8]))
    if refs:
        parts.append(
            "根拠参照: " + ", ".join(str(x.get("evaluation_id")) for x in refs[:8])
        )
    return "\n".join(parts)


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
    "format_match_summary",
    "format_clock",
    "label_counts",
    "parse_time_range",
    "time_range_text",
]
