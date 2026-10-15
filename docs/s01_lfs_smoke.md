# S-01: Git LFS match_001 point smoke

## Purpose and trust boundary

The opt-in `scripts/e2e/run_s01_lfs_smoke.py` entrypoint connects the source-verified
`match_001` LFS video to the existing **targeted isolated-point** E2E path.
It does **not** replace canonical full E2E, the independently qualified
continuous native R1/R2 lifecycle windows, or the formal S-01 acceptance gate.

By default it processes the seven frozen `round_boundary` points from
`datasets/e2e_suites/match_001/targeted.json`. The `--include-regressions`
flag expands the set to 16 distinct `round_boundary` / `regression_protection`
witnesses. The production recognizer, real calibration prefix and unchanged
point evaluator run; no synthetic event, round, or temporal interval is inferred.

The previously uploaded object is checked using its immutable source binding:

- Path: `tests/e2e/fixtures/real/match_001.mp4`
- SHA-256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`
- Length: `267056165` bytes

Missing files, unexpanded Git LFS pointers, symlinks, different lengths and
changed bytes are rejected **before** executing the recognizer. The independent
validation-pack manifest must have the same source SHA. The existing runner
checks the remaining profile, assertions, suite and provenance contracts.

## Local usage

Install Git LFS and use a checkout of `feat/s01-lfs-point-smoke` (or its
merged successor). The independent validation pack and qualified HUD layout
are still external and must be explicitly supplied:

~~~bash
git lfs install
git lfs pull --include=tests/e2e/fixtures/real/match_001.mp4

python scripts/e2e/run_s01_lfs_smoke.py \
  --validation-pack ValorantData/valorant_e2e_validation_pack_v3 \
  --hud-layout /path/to/validated/hud_layout.json \
  --preflight-only

python scripts/e2e/run_s01_lfs_smoke.py \
  --validation-pack ValorantData/valorant_e2e_validation_pack_v3 \
  --hud-layout /path/to/validated/hud_layout.json

# Only when more point coverage is needed:
python scripts/e2e/run_s01_lfs_smoke.py \
  --validation-pack ValorantData/valorant_e2e_validation_pack_v3 \
  --hud-layout /path/to/validated/hud_layout.json \
  --include-regressions
~~~

On Windows, run each command on a single PowerShell line or use PowerShell
backticks for continuation. Use `py -3.12` if `python` is not Python 3.12.

`--previous <previous-targeted-run>` and `--output <private-run-dir>`
are passed through to the existing compatibility and reporting logic.
Run artifacts remain under the normal ignored `outputs/e2e/` path unless
an explicit private output directory is provided.

## Results and guardrails

- Exit **0** means all *evaluated point fields* passed; inspect NOT_EVALUATED.
  It is not a lifecycle qualification or full E2E PASS.
- Exit **1** means point assertions failed, including known baseline failures.
  Compare the same fixed PTS/suite/profile and failure details before
  attributing a new regression.
- Exit **2** means input/preflight or pipeline failure.

R1 start/end and R2 start still require source-backed *continuous* evidence,
qualification and the canonical evaluation. No threshold changes, GT edits,
timestamp modifications, inferred player facts, or failure-to-PASS mappings
are allowed by this wrapper. A point smoke must not update the canonical
23 PASS / 55 FAIL / 4 NOT_EVALUATED baseline as if it were full E2E.

Ordinary CI and `pytest` run only pure contract tests, never the LFS video;
the opt-in script does not commit, push, or change existing profiles.
