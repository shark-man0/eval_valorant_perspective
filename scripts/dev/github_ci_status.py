#!/usr/bin/env python3
"""Read-only GitHub CI snapshot for VALORANT AI Coach.

Requires GitHub CLI (`gh`) on PATH and `gh auth login` already completed.

Examples:
  python3 scripts/dev/github_ci_status.py --pr 84
  python3 scripts/dev/github_ci_status.py --main
  python3 scripts/dev/github_ci_status.py --pr 84 --main --output ci-snapshot.json

Exit codes: 0=PASS, 1=FAIL, 2=PENDING/NOT VERIFIED, 3=CLI/API error.
No git fetch/pull/push or GitHub writes are performed.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_REPO = "shark-man0/eval_valorant_perspective"
CORE_WORKFLOWS = {"Basic CI", "Windows verification"}
WORKFLOW_JOB_FALLBACK = {
    "Basic CI": "linux-validation",
    "Windows verification": "test-and-build",
}
PASS_BUCKETS = {"pass", "skipping"}
FAIL_BUCKETS = {"fail", "cancel"}
SUCCESS_CONCLUSIONS = {"success"}
FAIL_CONCLUSIONS = {
    "failure",
    "cancelled",
    "timed_out",
    "action_required",
    "startup_failure",
    "stale",
}


class CliError(Exception):
    pass


def run_gh(*args: str, allow_check_exit: bool = False) -> Any:
    try:
        proc = subprocess.run(
            ["gh", *args], capture_output=True, text=True, check=False, encoding="utf-8", timeout=60
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CliError(f"GitHub CLI unavailable or timed out: {type(exc).__name__}") from exc
    if proc.returncode and not (allow_check_exit and proc.returncode in (1, 8)):
        raise CliError(
            f"gh {' '.join(args[:2])}: {proc.stderr.strip() or 'exit ' + str(proc.returncode)}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise CliError(
            f"gh {' '.join(args[:2])} returned invalid JSON: {proc.stderr.strip()}"
        ) from exc


def git_sha(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-fA-F]{40}", value) is None:
        raise CliError("GitHub returned an invalid commit SHA")
    return value.lower()


def status_of_checks(checks: list[dict[str, Any]]) -> str:
    if not checks:
        return "PENDING"
    buckets = [str(item.get("bucket", "")).lower() for item in checks]
    if any(bucket in FAIL_BUCKETS for bucket in buckets):
        return "FAIL"
    if any(bucket not in PASS_BUCKETS for bucket in buckets):
        return "PENDING"
    return "PASS"


def core_runs(
    repo: str,
    sha: str,
    events: set[str],
    *,
    branch: str | None = None,
    include_optional: bool = False,
) -> dict[str, dict[str, Any]]:
    """Require exact-SHA workflow evidence, not a similarly named job."""
    runs = run_gh(
        "run",
        "list",
        "-R",
        repo,
        "--commit",
        sha,
        *(["--branch", branch] if branch is not None else []),
        "--limit",
        "100",
        "--json",
        "headSha,headBranch,workflowName,status,conclusion,event,url,createdAt,databaseId",
    )
    if not isinstance(runs, list) or any(not isinstance(r, dict) for r in runs):
        raise CliError("gh run list did not return workflow entries")
    chosen: dict[str, dict[str, Any]] = {}
    for run in runs:
        name = run.get("workflowName")
        if (
            not isinstance(name, str)
            or not name
            or not include_optional
            and name not in CORE_WORKFLOWS
            or run.get("headSha") != sha
            or run.get("event") not in events
            or branch is not None
            and run.get("headBranch") != branch
        ):
            continue
        if name not in chosen or (
            str(run.get("createdAt") or ""),
            int(run.get("databaseId") or 0),
        ) > (str(chosen[name].get("createdAt") or ""), int(chosen[name].get("databaseId") or 0)):
            chosen[name] = run
    return chosen


def workflow_status(run: dict[str, Any] | None) -> str:
    if run is None or run.get("status") != "completed":
        return "PENDING"
    conclusion = str(run.get("conclusion") or "").lower()
    if conclusion in SUCCESS_CONCLUSIONS:
        return "PASS"
    return "FAIL" if conclusion in FAIL_CONCLUSIONS else "PENDING"


def combined(states: list[str]) -> str:
    return (
        "FAIL"
        if "FAIL" in states
        else ("PASS" if states and all(s == "PASS" for s in states) else "PENDING")
    )


def evaluate_pr(repo: str, number: int) -> dict[str, Any]:
    info = run_gh(
        "pr",
        "view",
        str(number),
        "-R",
        repo,
        "--json",
        "number,title,url,state,isDraft,headRefOid,baseRefOid,headRefName,baseRefName,mergeStateStatus,reviewDecision",
    )
    head_sha = git_sha(info.get("headRefOid"))
    checks = run_gh(
        "pr",
        "checks",
        str(number),
        "-R",
        repo,
        "--json",
        "name,state,bucket,workflow,link",
        allow_check_exit=True,
    )
    if not isinstance(checks, list):
        raise CliError("gh pr checks did not return a list")
    if not all(isinstance(c, dict) for c in checks):
        raise CliError("gh pr checks returned malformed check entries")
    chosen = core_runs(repo, head_sha, {"pull_request", "push"})
    workflows: dict[str, dict[str, Any]] = {
        name: {
            "state": workflow_status(chosen.get(name)),
            "run_id": chosen[name].get("databaseId") if name in chosen else None,
            "url": chosen[name].get("url") if name in chosen else None,
        }
        for name in sorted(CORE_WORKFLOWS)
    }
    missing = sorted(CORE_WORKFLOWS - chosen.keys())
    observed = run_gh("pr", "view", str(number), "-R", repo, "--json", "headRefOid")
    observed_sha = git_sha(observed.get("headRefOid"))
    status = combined([status_of_checks(checks), *[w["state"] for w in workflows.values()]])
    if observed_sha != head_sha:
        status = "PENDING"
    return {
        "type": "pull_request",
        "number": info.get("number"),
        "title": info.get("title"),
        "url": info.get("url"),
        "state": info.get("state"),
        "draft": info.get("isDraft"),
        "branch": info.get("headRefName"),
        "base": info.get("baseRefName"),
        "head_sha": head_sha,
        "observed_head_sha": observed_sha,
        "head_changed_during_read": observed_sha != head_sha,
        "workflows": workflows,
        "base_sha": info.get("baseRefOid"),
        "merge_state": info.get("mergeStateStatus"),
        "review_decision": info.get("reviewDecision"),
        "ci_status": status,
        "missing_core_workflows": missing,
        "checks": [
            {
                "name": c.get("name"),
                "workflow": c.get("workflow"),
                "state": c.get("state"),
                "bucket": c.get("bucket"),
                "url": c.get("link"),
            }
            for c in checks
        ],
    }


def evaluate_main(repo: str, branch: str) -> dict[str, Any]:
    # Branch endpoint reads the remote SHA; it does not trust stale local refs.
    branch_info = run_gh("api", f"repos/{repo}/branches/{branch}")
    sha = git_sha(branch_info.get("commit", {}).get("sha"))
    chosen = core_runs(repo, sha, {"push"}, branch=branch, include_optional=True)
    statuses: dict[str, dict[str, Any]] = {}
    for name in sorted(CORE_WORKFLOWS | set(chosen)):
        r = chosen.get(name)
        state = workflow_status(r)
        statuses[name] = {
            "state": state,
            "run_id": r.get("databaseId") if r else None,
            "url": r.get("url") if r else None,
            "conclusion": r.get("conclusion") if r else None,
        }
    all_states = [s["state"] for s in statuses.values()]
    ci_status = combined(all_states)
    observed = run_gh("api", f"repos/{repo}/branches/{branch}")
    observed_sha = git_sha(observed.get("commit", {}).get("sha"))
    if observed_sha != sha:
        ci_status = "PENDING"
    return {
        "type": "branch",
        "branch": branch,
        "head_sha": sha,
        "observed_head_sha": observed_sha,
        "head_changed_during_read": observed_sha != sha,
        "ci_status": ci_status,
        "workflows": statuses,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/repo")
    parser.add_argument("--branch", default="main", help="mainline branch to inspect")
    parser.add_argument("--pr", type=int, help="PR number to inspect")
    parser.add_argument("--main", action="store_true", help="also inspect remote mainline CI")
    parser.add_argument("--output", type=Path, help="optional JSON snapshot output file")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        parser.error("--repo must be owner/repo")
    if args.pr is not None and args.pr < 1:
        parser.error("--pr must be >= 1")
    if not re.fullmatch(r"[A-Za-z0-9_.\-/]+", args.branch):
        parser.error("invalid --branch")
    if shutil.which("gh") is None:
        print(
            "ERROR: GitHub CLI (gh) is missing. Install it and run `gh auth login`.",
            file=sys.stderr,
        )
        return 3
    report: dict[str, Any] = {
        "repo": args.repo,
        "checked_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "results": [],
    }
    try:
        if args.pr is not None:
            report["results"].append(evaluate_pr(args.repo, args.pr))
        if args.main or args.pr is None:
            report["results"].append(evaluate_main(args.repo, args.branch))
    except (CliError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    statuses = [result["ci_status"] for result in report["results"]]
    report["ci_status"] = (
        "FAIL"
        if "FAIL" in statuses
        else ("PASS" if all(s == "PASS" for s in statuses) else "PENDING")
    )
    print(f"Repository: {args.repo}")
    for r in report["results"]:
        descriptor = f"PR #{r['number']}" if r["type"] == "pull_request" else r["branch"]
        print(f"{descriptor}: {r['ci_status']} | SHA {r['head_sha']}")
        if r["type"] == "pull_request":
            print(
                f"  draft={r['draft']}, merge_state={r['merge_state']}, checks={len(r['checks'])}"
            )
            for c in r["checks"]:
                print(f"  - {c['bucket'] or '?':8} {c['workflow'] or '-'} / {c['name']}")
            if r["missing_core_workflows"]:
                print(f"  Missing core CI: {', '.join(r['missing_core_workflows'])}")
        else:
            for name, s in sorted(r["workflows"].items()):
                print(f"  - {s['state']:7} {name} | {s['url'] or 'no run'}")
    print("Overall CI:", report["ci_status"])
    print("Note: PASS is CI only, NOT a merge authorization (reviews/conflicts still apply).")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("Snapshot:", args.output)
    return {"PASS": 0, "FAIL": 1, "PENDING": 2}[report["ci_status"]]


if __name__ == "__main__":
    sys.exit(main())
