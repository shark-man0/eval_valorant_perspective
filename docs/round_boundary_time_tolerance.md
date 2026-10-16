# Round boundary timing policy

Start main: `7e480c2f2f7f49aea73e1541d065d78881d2f11c`.
Branch: `codex/round-boundary-time-tolerance`. This evaluator-only work does not modify PR #42's branch or S-01's transport/subject work.

## Contract audit

The existing `scripts/e2e/practical_accuracy.py` already scores independently reviewed **point** truth within ±0.1 seconds. It cannot substitute a midpoint for a source evidence bracket. Canonical v3 uses a different contract: generated point assertions contain `[last_absent - tolerance_before, first_present + tolerance_after]`. Per-item padding overrides defaults; the policy's default 0.1 does not replace an explicit 0.02, 0.03 or 0.05. Consequently a detected R1 end at 74.48600260416667 seconds lies about 0.003002604 seconds after its canonical window.

New evaluator profile **`round-boundary-bracket-0.1-v1`** replaces existing boundary padding with 0.1 on either side of the **raw evidence bracket**. It does not extend an already padded acceptance window. A zero-width bracket is a point and implements `abs(prediction - truth) <= 0.1`. No independently reviewed point truth is fabricated from a bracket. Distance to a bracket is zero inside it, otherwise distance to the nearer endpoint. This distance is not an absolute error against an independently known single onset.

The original point, bracket, per-item tolerance and generated assertion files remain byte-identical. The loader verifies the original window reconstructs from its raw annotation before creating an in-memory evaluator view. Missing, stale, ambiguous or foreign-round annotations fail closed. Only round_start/end point-event timing changes. Actors, required attributes, counts, ordering, negatives, discontinuities and all other predicates remain unchanged.

Point evaluation now uses decimal arithmetic on the serialized timestamps, replacing its former 1e-12 comparison epsilon. Exactly 0.1 passes; 0.101 and 0.1000000000005 fail. The additive point-report comparison version is `decimal-timestamp-0.1-v1`. Detector PTS and confirmation times are neither rounded nor moved.

## Safety and integration

`evaluate_trace()` retains its canonical default and report shape. Only the explicit timing-profile keyword enables the new evaluator view. `compare_boundary_timing` writes both original and new results with a version and input/code hashes. It never overwrites an existing result. Validation Pack files, trace, evaluator, schemas and local policy source hashes are checked before and after evaluation.

A timing PASS assumes an event legitimately released by its original producer. It is not proof of qualification, source continuity or current-code calibration. Unqualified Practical candidates are not promoted into formal events. Production start/end gates, qualification, ownership, confidence, source breaks and duplicate suppression are unchanged. Tests exercise the existing producer refusing an end when qualification is absent or the score/result evidence straddles a source break; time tolerance cannot restore that missing event. Existing end tests also cover weak/no result, spectator, menus, score conflicts and no invented second end.

No recognizer or sampler changes are included. A blanket 10fps change would need its own detection-recall and native-continuity experiment, particularly for short-lived signals. No speedup or signal coverage from such sampling is claimed. This work avoids re-decoding unchanged input because its hypothesis is exclusively about evaluator timing semantics.

## Archived match_001 targeted evaluation

The full saved trace of the **unadopted** native candidate was re-evaluated, including all 82 assertions. This is targeted evaluation replay, not newly recognized targeted video or a new Full E2E. Recognition remains attributed to the archived candidate and its original code/profile/qualification fingerprints. It is not relabeled as current-main recognition. No new source-continuous or match_002 qualification was run. match_001's source breaks remain relevant; it does not replace independent match_002 validation.

| Metric | Original policy | New timing policy | Delta |
| --- | ---: | ---: | ---: |
| PASS | 28 | 30 | +2 |
| FAIL | 50 | 49 | -1 |
| NOT_EVALUATED | 4 | 3 | -1 |
| Round starts | 2 | 2 | 0 |
| Round ends | 1 | 1 | 0 |
| Exact duplicate boundary records | 0 | 0 | 0 |
| Negative violations | 0 | 0 | 0 |
| Discontinuity violations | 0 | 0 | 0 |
| Evaluation seconds | 11.051 | 12.841 | +1.791 |

The only outcome changes are `GT-R1-ROUND-END` (FAIL → PASS) and `ordering_constraints-001` (NE → PASS). All 82 default outcomes and all default failure codes exactly reproduce the archived original report. The 20 negative assertions remain PASS. Timing-policy gain is +2 PASS; recognition improvement demonstrated here is **0**.

R1 start remains 4.102669270833333 seconds; R1 end remains 74.48600260416667; R2 start remains 111.4193359375. Both starts fall inside their raw review brackets (distance zero); the end is about 0.053002604 seconds outside its raw bracket and passes the new 0.1 allowance. Confirmation latency is not boundary error. No independently reviewed point onset error is claimed from these bracket annotations. The saved trace has no round_end at the later player-death scene and no fabricated R2 end; the new policy adds no events. Existing negatives remain the verified scope, not a proof of exhaustive false-positive absence.

The adopted formal baseline remains **23 / 55 / 4**. The archived candidate under its original criteria remains **28 / 50 / 4**. The new **30 / 49 / 3** is a separate timing-policy result and does not replace either baseline. A new canonical Full was not run because no detector or production pipeline changed; re-running ten hours of identical recognition would not test this evaluator-only hypothesis. New-policy source qualification and adoption remain separate review gates.

Only sanitized aggregate results and input hashes are committed in `e2e_reports/match_001/boundary_timing_policy_comparison.json`. Raw GT, images, profiles and trace remain private. Peak memory and recognition runtime changes were not measured; evaluation seconds are not a video speedup.

## Reproduce

From the checkout, with the project installed or `PYTHONPATH=src:.`:

```bash
python3 -m scripts.e2e.compare_boundary_timing \
  --pack /private/path/to/validation_pack \
  --trace /private/path/to/frozen/e2e_trace.json \
  --output outputs/boundary-timing/new-comparison.json
```

Exit 0 means the comparison completed; inspect both reports for assertion failures. The ordinary `tests/e2e/evaluate_saved_trace.py` command and full E2E commands retain their original canonical semantics. No GT or timing tolerance is passed into production recognition.

## Verification and remaining work

Local related unit/integration tests: **183 PASS in 56.63 seconds**. Ruff passes for src/tests/scripts/e2e; mypy passes 133 production source files. Updated Linux/Windows CI results are recorded on the dedicated PR. The test scope includes exact point offsets 0, 0.05, 0.1, 0.101, both signs, no widening epsilon, no double padding, immutable annotations, malformed/stale annotations, and existing source/qualification/lifecycle safety controls. Complete real-video requalification and independent match_002 boundary precision are not claimed. Current-frame state/identity and qualified Self Death remain separate S-01 blockers; a timing-policy gain cannot resolve them.
