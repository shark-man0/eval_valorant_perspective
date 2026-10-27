# Read-only CI snapshots

Use `scripts/dev/github_ci_status.py` for Map, HUD and source-management goals.
Until this branch is integrated, run it in the dedicated PR #99 checkout; do
not copy it into unrelated research branches. Requires authenticated GitHub CLI.

```sh
gh auth status
python3 scripts/dev/github_ci_status.py --pr 95 --main --output /private/tmp/ci-status.json
```

Use an approved private output directory for study receipts. Replace the PR
number with the actual target. Record its full `head_sha`, `observed_head_sha`,
the remote main SHA, workflow run IDs and exit code. One snapshot after a
functional milestone is sufficient. If the user will notify completion, do not
poll; retrieve each exact target after that notice.

Exit codes are `0 PASS`, `1 FAIL`, `2 PENDING / NOT VERIFIED`, `3 CLI/API error`.
Missing/skipped required workflows and changing HEADs are never green. Core
workflows require exact-SHA Actions evidence; a similarly named job cannot
stand in for a missing workflow. The snapshot rechecks the target ref after
reading checks. This bounds the read race, but is not an atomic GitHub snapshot
and does not promise the ref cannot change afterward.

PASS covers CI only. It is neither merge permission nor formal recognition
qualification. Check Linux/Windows test counts and Windows packaged launch
steps on the recorded run when those are required by the task. Main may have
different failures/cancellations from a PR; report each independently. Mocks
for failure/race states are not authenticated GitHub end-to-end verification.

The tool issues read commands only. Do not change authentication, rerun jobs,
cancel CI or alter branches merely to manufacture a test state.

Main snapshots require both the remote branch and SHA. A feature branch can
point to the same SHA; its later push/cancellation must not replace actual main
push evidence. Observed optional workflow failures on that same branch/SHA also
make the snapshot FAIL. Required workflows that are absent remain PENDING.

Use a fresh output file for each invocation. On CLI/API error an old output
file must not be interpreted as a new successful snapshot.
