# Lifecycle runtime readiness checkpoint

## Problem / target assertions

The source experiment has produced exposed continuous R1appearance links, but no independently qualified source profile. Determine whether a qualification report alone would activate the intended production scene/UI pipeline. Target remains GT-R1-ROUND-START/END, GT-R2-ROUND-START and related count/ordering predicates; historical conditional30PASSis not guaranteed. HEAD e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3.

## Evidence / root cause

Current `RealHudAnalyzer` creates `CompositeSourceContinuity` and emits `global_continuity` from actual camera/timer/phase. It filters externally supplied global/phase/result tokens. The paired lifecycle selects `global_scene_continuity` and `global_ui_transition` instead, requiring reviewed profile/code-bound qualification and current/prior native source provenance. No installed analyzer producer creates those two paired evidence fields. Therefore even a structurally valid paired report cannot make this production route emit a boundary. External diagnostic tokens must not be used to fill the gap.

The existing timer reader→HUD→native snapshot→trace display contract is implemented in models/builder/adapter. Source text/provenance are retained and compared; text is not regenerated from numeric seconds. Reimplementing that transport would repeat completed work. The remaining numeric blocker is qualified accepted image input, not loss of an already accepted display in transport.

The alternative nonself killfeed snapshot field is still missing, but current pixel insertion plus roster decrease can produce an anonymous row only. It does not establish nonself ownership/name semantics. Copying row insertion to `nonself_killfeed_row_visible=true` would invent a fact. No such export is added.

The nine known-disjoint source frames from the preceding PTS-gap reservation all yielded0reference correspondences/seeds. They cannot qualify positive continuity or establish the source-view generalization needed by the paired runtime producer. The delayed observer's19links/5critical transient links are exposed development only, not runtime world/hidden-time attestation.

## Contract change

Add one startup profile diagnostic **only when a paired qualification successfully loads**: `runtime scene/UI evidence producer is not installed; scene-transition boundaries remain unavailable`. Qualification loading/components, readers, thresholds, evidence overwrite policy, lifecycle and production recognition decisions are unchanged. Legacy composite/no-qualification setups do not receive this new notice. This makes the missing producer actionable before an unnecessary full E2E.

The HUD code fingerprint necessarily changes with this instrumentation. Qualification reports must retain the normal current-code binding; old fingerprints are not grandfathered or rewritten. No adopted global qualification is added or changed.

## Tests

102global lifecycle/paired UI/composite continuity/timer-display contract tests PASS in12.94seconds. New tests verify the diagnostic appears for a valid paired synthetic report only and does not discard/change its qualification/components. Existing tests exercise untrusted proof rejection, timer transition safety, phase duration, duplicate/cut/epoch rejection, system actor and native/trace contracts. Synthetic reports remain unit fixtures, not real qualification.

Ruff PASS; mypy PASS on104source files; diff checks PASS. No fresh targeted/sampled/full E2E: there is no independently qualified real input or installed paired source producer. Windows execution is unverified.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Installed paired scene/UI producer |Absent|Absent; startup diagnostic added|0producers|
| Accepted paired qualification components in unit fixture |Unchanged set|Unchanged set|0|
| Runtime qualification from current video |0|0|0|
| Canonical PASS/FAIL/NE |Historical23/55/4|Not rerun|Unmeasured|

All82historical assertion entries remain unchanged. This checkpoint fixes observability, not any assertion. Negative/discontinuity historical0/0is not claimed freshly measured by full E2E. Machine-readable code bindings and results are in `e2e_reports/match_001/lifecycle_runtime_readiness.json`.

## Remaining blocker / next implementation

Stop interpreting additional isolated appearance success as sufficient readiness. The next vertical work is an actual qualified native scene/UI producer→analyzer adapter: it must own current/prior PTS/pixels, emit neither proof nor prior history while acquisition is unavailable, reject gaps/cuts/rejoin, preserve every observed display and phase-disappearance provenance, and bind independent world/source/UI qualification. Qualification remains absent, so any future implementation must default to empty evidence until that gate is met; a diagnostic link cannot be relabelled `background_checked=true` or made an attestation by dictionary conversion.

R1scene/UI evidence remains the first acceptance focus. Source qualification, R1end banner/corroboration, R2start application, native packages and canonical acceptance are incomplete. Avoid more arbitrary holdout windows or descriptor variants without a concrete producer/source eligibility hypothesis.
