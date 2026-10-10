# Production contract regression checkpoint

## Problem and evidence

Source-assured lifecycle, decoder tick/cache identity, native timer transport,
spectator snapshot transport and source-break handling have accumulated shared
production changes. Targeted tests alone do not verify the complete repository
test suite. This checkpoint checks the combined worktree at HEAD
`e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3` without running real-video full E2E.

`pytest -q` with `PYTHONPATH=.:src` and `VALORANT_E2E_VALIDATION_PACK` set to
`ValorantData/valorant_e2e_validation_pack_v3` produces2459PASS/1FAIL/9SKIP
in1728.56seconds. The sole failure is a Visual semantic integration mock that
does not accept the new `continuity_breaks` keyword. It fails before exercising
semantic event confirmation/resume, so that behavior was not verified by the
initial run. Ruff on `src tests scripts/e2e` and mypy on121source files PASS.

## Root cause and change

The `_measure` fixture now explicitly accepts `continuity_breaks` and asserts
the empty tuple expected for its uninterrupted source. It does not silently
ignore arbitrary break lists. Production APIs, thresholds, lifecycle evidence,
Validation Pack and assertion semantics are unchanged by this fixture repair.

## Tests

The entire Visual runtime integration module and three validation-pack integration
modules are rerun with BOTH `VALORANT_E2E_PACK` and
`VALORANT_E2E_VALIDATION_PACK` pointing to the same supplied pack. All13tests PASS
in20.64seconds, with no skips. This includes the repaired semantic confirmation/
resume test, canonical evaluator/share reconciliation, shot contract and pack
validation/production leakage checks. Three initially skipped external-pack
tests are now executed. Full repository Ruff remains PASS.

| Verification | Previous | Current | Delta |
| --- | --- | --- | --- |
| Known regression test failure | 1 | 0 after related rerun | -1 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | Not rerun | Unavailable |
| Released qualified lifecycle events | 0 | 0 | 0 |

The whole suite was not rerun after this test-only repair;2459initial passes
and13followup passes are overlapping scopes and must not be summed or reported
as a single green full-suite run. Initial remaining skips concern optional real
HUD acceptance, local Tesseract, Windows path handling and PowerShell. Windows
hardware remains unverified. The optional real-video test is not enabled to
silently introduce an additional long recognition run.

## Remaining blocker

A green unit/integration contract cannot qualify current-image lifecycle inputs.
Known R1/R2start development windows remain development data, not independent
positive temporal holdout. The loader requires3distinct reviewed source hashes
per split, not3distinct round episodes. No image-based no-edit proof is required
for the exact assured source. Reader/UI qualification, result generalization and
end timestamp semantics remain unresolved; no qualification report is minted
and no new canonical targeted/sampled/full acceptance is claimed.

Machine-readable evidence: `e2e_reports/match_001/production_contract_regression_check.json`.
Terminal logs are saved locally under
`outputs/recognition-investigation/regression-check-20261010`, with hashes in the
report. All82canonical assertion statuses are unchanged.
