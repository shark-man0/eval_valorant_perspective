# Read-only GitHub CI snapshots

Use `scripts/dev/github_ci_status.py` from the dedicated tool checkout; it is
independent of HUD recognition experiments. Do not copy or merge the tool into
an experiment merely to inspect CI.

```sh
gh auth status
python3 scripts/dev/github_ci_status.py --pr 93 --main --output /private/output/ci.json
```

Use an existing restricted Private output directory for research. The command
reads GitHub and writes the local report. It does not push, create/review a PR,
rerun workflows, merge, or grant release approval. Do not print authentication
tokens or inject credentials into a report.

Exit codes: 0 PASS, 1 FAIL, 2 PENDING/unverified, 3 CLI/API error. A report that
was not produced is not PASS. Preserve the command exit code, tool revision,
PR HEAD, branch HEAD and snapshot time alongside the output. If API access
fails, an older output file is not evidence for the failed invocation; use a
fresh output path for each snapshot.

The required workflows are Basic CI and Windows verification. Missing or
entirely skipped required workflows remain PENDING. Failure takes precedence
over pending/success. The remote branch endpoint is authoritative, not a local
main ref. A push on a different branch with the same SHA must not replace the
main run. Additional observed branch workflow failures are also FAIL.

PR metadata and checks are separate requests: core Actions runs must target the
same head SHA. The tool rejects a HEAD change during acquisition. This is a
bounded snapshot, not a continuously atomic promise; retrieve again explicitly
after a new head or a user completion notice. Do not poll repeatedly.

The summary does not substitute for required check diagnostics. Inspect exact
SHA Windows job steps for packaging and packaged `--smoke-test`, plus any Text
I/O, coverage, annotation or task-specific gates. CI PASS is never merge or
qualification authorization.

Live validation of the original PR exposed a branch-selection defect: main's
SHA was also pushed on a feature branch, and that branch's later cancelled runs
overrode successful main runs. The fix filters both branch and SHA. Mock
tests additionally cover missing workflows and moving/mismatched HEADs; mocks
are not live evidence of those GitHub states.
