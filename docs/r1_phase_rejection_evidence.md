# R1 phase rejection evidence

## Problem

At HEAD `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`, the qualified scene/UI lifecycle consumes an explicit phase-disappearance proof, but the installed semantic text matcher establishes presence only. The previous runtime-readiness audit identified the missing scene/UI producer. Its implementation must also distinguish unreadable phase input from verified disappearance. Target assertions remain `GT-R1-ROUND-START`, `GT-R1-ROUND-END`, `GT-R2-ROUND-START` and their count/ordering predicates.

## Evidence / competing hypotheses

Previously, a nonmatch discarded the group scores. It could represent changed letters, flat/occluded glyph regions, or invalid ROI dimensions. Absence of a positive flag cannot establish which happened. A same-scene visual link also does not independently prove uninterrupted game time.

Add optional semantic diagnostics using the existing masked NCC function, threshold and contrast requirement. Record each group's score, current contrast and mask population, actual pixel bounds and raw crop hash. Keep presence unknown for every nonmatch. Explicitly mark `absence_checked=false` and `runtime_transition_authorized=false`. Analyzer diagnostic payloads now bind measurements to actual image hash and observation PTS. These measurements do not enter classification, lifecycle evidence, snapshots or trace assertions.

## Independent image evidence

Replay the existing exposed 30 native R1 images from `native-global-preparation-complete-20261008/window-000`. Verify each PNG hash and decoded pixel hash against the existing source report; verify source report/profile hashes again at completion. No Validation Pack is loaded. Both diagnostic and ordinary template calls return exactly equal signals for all 30 images. This is development evidence, not holdout qualification.

| Measurement | Value |
| --- | ---: |
| Verified saved native images |30|
| Phase presence matches |12|
| Unknown nonmatches |18|
| Groups rejected for unavailable contrast |54|
| Groups rejected only for below-threshold appearance |0|

At the last matching PTS 4.086003, the three groups have current standard deviations 25.69814, 27.14181 and 26.89186. At 4.102669, these become 0.69750, 0.87805 and 0.18514. All are below the unchanged contrast floor of 5. The actual ROI is `[765,170,1155,240]`. The masked glyph support becomes nearly flat before the previously observed timer display transition. This is distinct from a textured but mismatching text group.

## Continuity decision / contract change

No new continuity decision or boundary is authorized. Flat glyph masks alone cannot distinguish phase disappearance from covering/obscuring content or independently rule out a scene cut. Do not convert score zero, missing phase flags or these diagnostics into `global_ui_transition`. The existing fail-closed scene/UI gate remains intact. No timer/score/reference/geometry policy change, GT injection or qualification report is introduced. HUD code fingerprints change normally; old qualification is not grandfathered.

The optional API is `profile.detect_signals(frame, layout, semantic_diagnostics=records)`. Without a diagnostics sink, the analyzer keeps the original scoring route and does not compute diagnostic source hashes. Configured but unavailable ROIs are explicitly unknown; missing or invalid references cannot manufacture measurements. `SemanticTextReference.measure` preserves the exact score used by recognition.

## Tests

134 related semantic text, HUD replay, global lifecycle, qualified UI, composite continuity and timer-display tests pass in 13.65 seconds. Tests cover matched/wrong/flat/dimension-mismatched groups, missing ROI, unchanged signal output and source binding. Ruff on `src tests scripts/e2e` and mypy on all 104 source files pass. Saved-image replay takes 41.214979 seconds, including two equivalent template calls per image; this is not an E2E runtime comparison.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| R1 nonmatch rejection details |Discarded|18 images / 54 low-contrast groups measured|New diagnostic evidence|
| Signals changed on replay |Not measured|0 / 30|No decision changes|
| Independently qualified scene/UI producer |0|0|0|
| Canonical PASS / FAIL / NE |23 / 55 / 4|Not rerun|Unmeasured|

All 82 historical assertion entries remain unchanged. Full/targeted/sampled canonical E2E is not run because no qualified acceptance candidate exists. Historical negative/discontinuity counts 0/0 are not claimed newly measured. Windows execution remains unverified.

## Remaining blocker

An actual source-owned scene producer and independent phase-absence qualification are still required. The present matcher deliberately proves presence only. A valid UI producer must measure current absence or transition with its own reviewed negative/holdout controls, preserve native source continuity and retain all observed clock displays. Merely adapting diagnostic dictionaries would fabricate authorization. Resolve this source contract before another matcher variant or full E2E.

Machine-readable evidence: `e2e_reports/match_001/r1_semantic_measurements.json`.
