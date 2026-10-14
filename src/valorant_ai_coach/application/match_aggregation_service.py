"""Reconstruct a conservative MatchAggregator view from canonical SQLite rows.

Only persisted Round Packages and evaluations are considered. No missing output,
expected Round number, temporal scope, confidence, or score is inferred.
"""
from __future__ import annotations

from typing import Any

from valorant_ai_coach.storage import SQLiteRepository

from .match_aggregation import MatchAggregationError, MatchAggregator, RoundInput
from .round_analyzer import RoundAnalyzer

_FULL_SET_MARKER = "full_post_dedup_v1"


def _round_numbers(value: object) -> set[int]:
    if not isinstance(value, list):
        return set()
    return {
        number
        for number in value
        if isinstance(number, int) and not isinstance(number, bool) and number >= 1
    }


def _boundary_uncertain_or_invalid(package: dict[str, Any]) -> bool:
    """Malformed lifecycle must not crash history/JSON report read paths."""
    try:
        return RoundAnalyzer.boundary_context_is_uncertain(package)
    except (KeyError, TypeError, ValueError):
        return True


def aggregate_saved_match(repository: SQLiteRepository, match_id: str) -> dict[str, Any]:
    """Recalculate from stored rows and explicitly expose any unverifiable state.

    Output envelopes lost by SQLite's v1 row-wise storage are reconstructed solely
    for contract validation, using the same RESTORED envelope as Pipeline._restore_round.
    An absent evaluation is never reconstructed. A saved Round lacking a checkpoint
    and any evaluations is *not_evaluated*, not an assumed empty successful Round.
    """
    if repository.get_match(match_id) is None:
        raise KeyError(f"matchがありません: {match_id}")
    packages = repository.list_round_packages(match_id)
    evaluations = repository.list_evaluations(match_id)
    checkpoint_row = repository.get_job_checkpoint(match_id)
    checkpoint = (checkpoint_row or {}).get("checkpoint", {})
    if not isinstance(checkpoint, dict):
        checkpoint = {}
    completed = _round_numbers(checkpoint.get("completed_rounds"))
    failed = _round_numbers(checkpoint.get("failed_rounds"))
    inputs: list[RoundInput] = []
    seen: set[int] = set()
    for package in packages:
        if not isinstance(package, dict) or package.get("match_id") != match_id:
            raise MatchAggregationError("保存済みRound Packageのmatch_idが不正です")
        round_no = package.get("round_no")
        if (
            isinstance(round_no, bool)
            or not isinstance(round_no, int)
            or round_no < 1
            or round_no in seen
        ):
            raise MatchAggregationError("保存済みRound Packageのround_noが不正です")
        seen.add(round_no)
        stored = repository.list_round_evaluations(match_id, round_no)
        reason: str | None = None
        output: dict[str, Any] | None = None
        if round_no in failed:
            reason = "失敗したRoundの保存済み評価は採用しません"
        elif _boundary_uncertain_or_invalid(package):
            if stored:
                # A valid Practical Round with scores is a storage-contract violation.
                raise MatchAggregationError(
                    f"R{round_no}: 境界未確定または不正なのに採点済み評価が保存されています"
                )
            reason = "Practical/unknownまたは不正な境界のため採点保留"
        elif stored or round_no in completed:
            output = {
                "schema_version": "3.0",
                "analysis_id": f"RESTORED-{match_id}-R{round_no}",
                "match_id": match_id,
                "round_no": round_no,
                "evaluations": stored,
            }
        else:
            reason = "評価結果または完了チェックポイントがありません"
        if round_no in failed:
            reason = "保存済みRoundの解析失敗（詳細はジョブ診断に記録）"
        inputs.append(
            RoundInput(round_package=package, output=output, evaluation_failure=reason)
        )
    orphan = [
        str(row.get("evaluation_id", "unknown"))
        for row in evaluations
        if row.get("round_no") not in seen
    ]
    if orphan:
        raise MatchAggregationError(
            "対応するRound Packageのない評価が保存されています: "
            + ", ".join(sorted(orphan)[:8])
        )
    view = MatchAggregator().aggregate(
        inputs, match_id=match_id, expected_round_numbers=None
    ).to_dict()
    # On post-L5 data, reaching the UI budget cannot imply missing stored
    # records. Keep the measured per-rule counts/limit flags unchanged, but
    # remove the *legacy truncation* warning for this proven complete input.
    if checkpoint.get("canonical_evaluation_set") == _FULL_SET_MARKER:
        view["issues"] = [
            item for item in view["issues"]
            if item["code"] != "display_limit_reached"
        ]
    missing_failed = sorted(failed - seen)
    missing_completed = sorted(completed - seen)
    for code, missing, detail in (
        (
            "failed_round_package_missing",
            missing_failed,
            "失敗したRoundの保存済みPackageがありません",
        ),
        (
            "completed_round_package_missing",
            missing_completed,
            "完了記録のあるRoundの保存済みPackageがありません",
        ),
    ):
        if not missing:
            continue
        # Never infer the data of a Round whose existence is only checkpointed.
        completeness = view["completeness"]
        completeness["status"] = "incomplete"
        completeness["blocking_reasons"] = sorted(
            set(completeness["blocking_reasons"]) | {code}
        )
        view["issues"].extend({
            "code": code,
            "round_no": number,
            "rule_id": None,
            "evaluation_id": None,
            "detail": detail,
        } for number in missing)
    view["storage_provenance"] = {
        "source": "sqlite_recomputed",
        "saved_evaluation_set": (
            _FULL_SET_MARKER
            if checkpoint.get("canonical_evaluation_set") == _FULL_SET_MARKER
            else "legacy_or_unverified"
        ),
        "candidate_scopes_restored": False,
        "missing_failed_round_packages": missing_failed,
        "missing_completed_round_packages": missing_completed,
    }
    return view
