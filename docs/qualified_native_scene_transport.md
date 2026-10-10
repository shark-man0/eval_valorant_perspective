# Qualified native scene transport

## Problem / target

Common native source measurements existed, but there was no production entrance to transport separately qualified scene-only evidence in the lifecycle's source contract. R1 start remains the first target, with round count/order/package dependencies. The image qualification and current UI disappearance blockers are not solved by transporting measurements.

HEAD: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.

## Change

`RealHudAnalyzer.collect_qualified_native_scene_window` is an explicit native API. It requires configured source assets and the analyzer's loaded global qualification. The internal collector reloads the report against the analyzer's current complete base fingerprint, requires paired `scene_continuity` / `ui_transition` qualification and consumes actual `NativeSourceFrame` inputs through the unchanged common native scene measurement path. Missing, legacy or stale qualification is rejected before any proof can be released.

The scene qualification's reviewed cases must cover the complete producer, including current background eligibility, acquisition, source continuity and independent negative controls. Valid asset hashes or appearance counts alone do not supply that qualification. No report is generated, re-signed or installed by this change.

Supported links carry actual current/previous integer PTS, time base, pixel hashes, source video hash, decoder-owned epoch, source-profile hash and qualification/code/config fingerprints. Seed/pending/terminated rows release no proof. The segment includes the actual decoder epoch, so separate decode windows cannot masquerade as one continuous source stream.

All original reviewed domains remain in the underlying measurement. Domains sharing a spatial cell are aggregated using their **minimum** NCC, never their maximum. The resulting distinct cells must satisfy the existing lifecycle's three-cell/two-row/two-column and NCC≥0.90 contract. Native previous-frame time/pixels are preserved; they are not relabeled to match a sampled observation. Invalid measured source-region/provenance data is rejected. Each domain score must be finite, numeric (excluding booleans) and ≥0.90 before cell aggregation, so a NaN or rejected domain cannot be hidden behind another domain in the same cell.

Results are buffered until terminal checks revalidate source-profile/reference assets, every encoded/decoded native frame, qualification report bytes and recognition code fingerprint. Mutation raises an error without returning buffered proofs.

## Behavior and scope

This API produces only `system_scene_evidence.global_scene_continuity`. It consumes no timer, score, phase value, expected timestamp, round ID or Validation Pack. It creates no UI disappearance proof, boundary, event, round package, HP/weapon/death/player fact or world-mask authorization for other recognizers.

The existing diagnostic native API and default sampled/full orchestration remain unchanged. This entrance is not automatically called by canonical E2E. The complete paired scene/UI runtime producer is still incomplete, so the analyzer's existing missing-producer diagnostic remains appropriate. External supplemental dictionaries still cannot inject qualified scene/UI evidence into normal HUD analysis.

Adding production code changes the existing recognizer fingerprint. Old qualification and code-bound development reports do not inherit the new fingerprint; they must not be silently re-signed or described as current qualified measurements.

## Evidence / tests

Ten new transport tests use **synthetic qualification and mocked scene calculations**, checking provenance, lowest-score cell aggregation, lifecycle source-contract compatibility, absent/legacy qualification rejection, mutated report/reference/native input rejection and previous-frame mismatch. They are contract tests, not evidence of real image accuracy or successful holdout.

With native source-input, source-binding and global lifecycle tests: **65 passed in 35.44 seconds**. Ruff passed for `src tests scripts/e2e`; mypy passed for **113 source files**. The initial test run had a missing reused fixture import, which was corrected before the passing run.

[The real-input guard verification](../e2e_reports/match_001/native_scene_evidence_guard_verified.json) reads two actual saved native frames and validates their image hashes. The analyzer's actual default qualification path is absent. The new API rejects with `bound scene assets and global qualification required`; scene proofs, UI proofs and events released are all zero. No synthetic report is applied to those real frames. This is a qualification guard check, not a positive scene-recognition or full E2E result.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Explicit qualified native scene transport APIs | 0 | 1 | +1 |
| Adopted real paired scene/UI qualification | 0 | 0 | 0 |
| Complete paired scene/UI runtime producer | 0 | 0 | 0 |
| Proofs/events released in real unqualified guard | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 historical | Unmeasured | Unmeasured |

No standard targeted/sampled/full E2E is run: no independently qualified three-boundary candidate exists. Canonical round/package/negative/discontinuity/runtime figures are unmeasured; the archived baseline is not relabeled as a new run. All 82 archived assertion entries remain unchanged.

## Remaining blockers / next implementation

1. Independently qualify actual source acquisition/current background eligibility and continuity; the previous doorway development proposal failed.
2. Implement and independently qualify current UI disappearance, retaining the distinction between unknown text and absent panel.
3. Deliver native timer/phase observations and source proofs to a separately owned native system lifecycle; merge resulting events into packages/trace without changing full sampling or borrowing native previousPTS for sampled frames.
4. Validate R1 start first, then R2 start and the separately qualified result-banner/end path, preserving negative/discontinuity safety before canonical evaluation.

This transport API does not complete the round lifecycle milestone. Windows native decoder/OpenCV/asset-path behavior remains unverified on Windows.
