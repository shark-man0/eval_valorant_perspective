"""Read-only snapshot guards: real branch/SHA and missing evidence."""

from __future__ import annotations

from typing import Any

import pytest

from scripts.dev import github_ci_status as ci

SHA = "a" * 40


@pytest.mark.parametrize(
    ("buckets", "expected"),
    [
        ([], "PENDING"),
        (["pass"], "PASS"),
        (["pass", "pending"], "PENDING"),
        (["pass", "fail"], "FAIL"),
        (["fail", "pending"], "FAIL"),
        (["skipping"], "PASS"),
        (["unknown"], "PENDING"),
    ],
)
def test_classification(buckets: list[str], expected: str) -> None:
    assert ci.status_of_checks([{"bucket": b} for b in buckets]) == expected


def test_main_same_sha_other_branch_is_not_main(monkeypatch: pytest.MonkeyPatch) -> None:
    def gh(*args: str, **kw: Any) -> Any:
        if args[0] == "api":
            return {"commit": {"sha": SHA}}
        return [
            {
                "headSha": SHA,
                "headBranch": branch,
                "workflowName": w,
                "status": "completed",
                "conclusion": conclusion,
                "event": "push",
                "createdAt": date,
            }
            for w in ci.CORE_WORKFLOWS
            for branch, conclusion, date in [
                ("main", "success", "2026-01-01"),
                ("research", "cancelled", "2026-02-01"),
            ]
        ]

    monkeypatch.setattr(ci, "run_gh", gh)
    assert ci.evaluate_main("owner/repo", "main")["ci_status"] == "PASS"


@pytest.mark.parametrize(
    ("run_sha", "changed", "expected"),
    [
        (SHA, False, "PASS"),
        ("b" * 40, False, "PENDING"),
        (SHA, True, "ERROR"),
    ],
)
def test_pr_native_sha_and_moving_head(
    monkeypatch: pytest.MonkeyPatch, run_sha: str, changed: bool, expected: str
) -> None:
    def gh(*args: str, **kw: Any) -> Any:
        if args[0] == "api":
            return {"head_sha": run_sha, "status": "completed", "conclusion": "success"}
        if args[1] == "view":
            current = args[-1] == "headRefOid"
            return {"number": 1, "headRefOid": "c" * 40 if current and changed else SHA}
        return [
            {
                "workflow": w,
                "bucket": "pass",
                "link": "https://github.com/owner/repo/actions/runs/123/job/456",
            }
            for w in ci.CORE_WORKFLOWS
        ]

    monkeypatch.setattr(ci, "run_gh", gh)
    if expected == "ERROR":
        with pytest.raises(ci.CliError, match="HEAD changed"):
            ci.evaluate_pr("owner/repo", 1)
    else:
        assert ci.evaluate_pr("owner/repo", 1)["ci_status"] == expected


def test_all_skipped_core_is_missing() -> None:
    assert not ci.core_check_present([{"workflow": "Basic CI", "bucket": "skipping"}], "Basic CI")


def test_successful_optional_only_pr_is_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    def gh(*args: str, **kw: Any) -> Any:
        if args[1] == "view":
            return {"headRefOid": SHA}
        return [{"workflow": "optional", "bucket": "pass"}]

    monkeypatch.setattr(ci, "run_gh", gh)
    result = ci.evaluate_pr("owner/repo", 1)
    assert result["ci_status"] == "PENDING"
    assert set(result["missing_core_workflows"]) == ci.CORE_WORKFLOWS


def test_optional_main_workflow_failure_is_not_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    def gh(*args: str, **kw: Any) -> Any:
        if args[0] == "api":
            return {"commit": {"sha": SHA}}
        return [
            {
                "headSha": SHA,
                "headBranch": "main",
                "workflowName": w,
                "status": "completed",
                "conclusion": "failure" if w == "extra" else "success",
                "event": "push",
                "createdAt": "2026-01-01",
            }
            for w in ci.CORE_WORKFLOWS | {"extra"}
        ]

    monkeypatch.setattr(ci, "run_gh", gh)
    assert ci.evaluate_main("owner/repo", "main")["ci_status"] == "FAIL"
