"""Offline CI status contracts; live GitHub verification is separate."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "ci_snapshot", Path(__file__).resolve().parents[2] / "scripts/dev/github_ci_status.py"
)
assert SPEC and SPEC.loader
ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci)
SHA, NEW = "a" * 40, "b" * 40


def info(sha=SHA):
    return {"number": 95, "headRefOid": sha, "baseRefOid": "c" * 40, "isDraft": True}


def checks(bucket="pass"):
    return [
        {"workflow": n, "name": job, "bucket": bucket}
        for n, job in ci.WORKFLOW_JOB_FALLBACK.items()
    ]


def runs(state="completed", conclusion="success", sha=SHA):
    return [
        {
            "workflowName": n,
            "status": state,
            "conclusion": conclusion,
            "headSha": sha,
            "event": "pull_request",
            "createdAt": "2026-10-27T00:00:00Z",
            "databaseId": i,
        }
        for i, n in enumerate(sorted(ci.CORE_WORKFLOWS), 1)
    ]


def fake(monkeypatch, *, current=SHA, workflow_runs=None, returned_checks=None):
    calls = []

    def gh(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("pr", "view"):
            return info(SHA if sum(a[:2] == ("pr", "view") for a in calls) == 1 else current)
        if args[:2] == ("pr", "checks"):
            return checks() if returned_checks is None else returned_checks
        if args[:2] == ("run", "list"):
            return runs() if workflow_runs is None else workflow_runs
        raise AssertionError(args)

    monkeypatch.setattr(ci, "run_gh", gh)
    return calls


def test_changed_pr_head_never_inherits_old_green_checks(monkeypatch):
    fake(monkeypatch, current=NEW)
    result = ci.evaluate_pr("owner/repo", 95)
    assert result["ci_status"] == "PENDING"
    assert result["head_sha"] == SHA
    assert result["observed_head_sha"] == NEW


def test_success_checks_without_exact_sha_workflows_are_pending(monkeypatch):
    fake(monkeypatch, workflow_runs=runs(sha=NEW))
    assert ci.evaluate_pr("owner/repo", 95)["ci_status"] == "PENDING"


def test_job_name_cannot_impersonate_required_workflow(monkeypatch):
    fake(
        monkeypatch,
        returned_checks=[{"workflow": "unrelated", "name": "linux-validation", "bucket": "pass"}],
        workflow_runs=[],
    )
    assert ci.evaluate_pr("owner/repo", 95)["ci_status"] == "PENDING"


@pytest.mark.parametrize(
    "state,conclusion,expected",
    [
        ("completed", "success", "PASS"),
        ("completed", "failure", "FAIL"),
        ("completed", "cancelled", "FAIL"),
        ("completed", "skipped", "PENDING"),
        ("in_progress", "", "PENDING"),
        ("queued", "", "PENDING"),
    ],
)
def test_exact_pr_workflow_states(monkeypatch, state, conclusion, expected):
    fake(monkeypatch, workflow_runs=runs(state, conclusion))
    assert ci.evaluate_pr("owner/repo", 95)["ci_status"] == expected


def test_duplicate_workflow_attempt_uses_latest(monkeypatch):
    rr = runs() + [
        {
            **r,
            "createdAt": "2026-10-27T01:00:00Z",
            "conclusion": "failure",
            "databaseId": 10 + r["databaseId"],
        }
        for r in runs()
    ]
    fake(monkeypatch, workflow_runs=rr[::-1])
    assert ci.evaluate_pr("owner/repo", 95)["ci_status"] == "FAIL"


def test_api_failure_is_cli_error(monkeypatch):
    monkeypatch.setattr(
        ci.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 1, "", "authentication failed"),
    )
    with pytest.raises(ci.CliError):
        ci.run_gh("api", "repos/owner/repo")


@pytest.mark.parametrize("data", ["notjson", "{}"])
def test_bad_response_is_not_green(monkeypatch, data):
    if data == "notjson":
        monkeypatch.setattr(
            ci.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 0, data, "")
        )
        with pytest.raises(ci.CliError):
            ci.run_gh("api", "repos/owner/repo")
    else:
        fake(monkeypatch, workflow_runs={})
        with pytest.raises(ci.CliError):
            ci.evaluate_pr("owner/repo", 95)


@pytest.mark.parametrize(
    "bucket,expected",
    [("pass", "PASS"), ("fail", "FAIL"), ("cancel", "FAIL"), ("pending", "PENDING")],
)
def test_buckets(bucket, expected):
    assert ci.status_of_checks([{"bucket": bucket}]) == expected


def test_no_checks_is_pending():
    assert ci.status_of_checks([]) == "PENDING"


def test_remote_main_race_is_pending(monkeypatch):
    count = 0

    def gh(*args, **kwargs):
        nonlocal count
        if args[:2] == ("api", "repos/owner/repo/branches/main"):
            count += 1
            return {"commit": {"sha": SHA if count == 1 else NEW}}
        return [{**r, "event": "push"} for r in runs()]

    monkeypatch.setattr(ci, "run_gh", gh)
    assert ci.evaluate_main("owner/repo", "main")["ci_status"] == "PENDING"
