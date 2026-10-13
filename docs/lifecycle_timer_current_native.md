# Current native timer evidence and joint split audit

## Problem and target

The assured start path still needs supportedtimerandui_transitionalongside
purchase_phase. Targets areGT-R1-ROUND-START,GT-R2-ROUND-START,
event_count_constraints-000,event_count_constraints-004andordering_constraints-001.
Old reader reports cannot be re-signed under current code or changed image
formats; raw accepted timer text must remain independently source reviewed.

## Evidence and frozen method

All ten digit PNG hashes in the existing strict timer profile exactly match
references selected by the original Gaussian training report. NCC0.90, class
margin0.04, Gaussian3×3comparison, colon/shape gates and subregion are unchanged.
The old cohort has64physical training frames plus12additional training frames,
with the frozen32physical holdout sources disjoint from all76training ticks.
No reference, candidate, OCR fallback or production code is added.

Select the same32reviewed cases before current predictions, using nearest native
tick to the old rounded review PTS. VideoService verifies each exact tick and
source SHA. The current native contact sheet agrees with all32old source display
labels, including weak/overlaid examples. It is reviewed before current reader
predictions. These are already exposed source cases; conversion to native PNG
does not create a new blind holdout or independent-video validation.

Read current JPEG and native PNG through the same frozen shared reader at the
explicit nominal layout ROI. A first diagnostic invocation incorrectly used
application crop_roi without calibration and was rejected before any prediction.
The corrected static diagnostic reads declared normalized coordinates directly;
no fake calibration or application guard bypass is introduced. This is not a
current-calibrated full analyzer or continuous event test.

## Tests and Previous / Current / Delta

| Metric | Previous historical JPEG | Current native PNG | Delta |
| --- | ---: | ---: | ---: |
| Correct timer displays | 25 | 25 | 0 |
| Unknown | 7 | 7 | 0 |
| Wrong accepted values | 0 | 0 | 0 |
| Physical verification cases | 32 | 32 | 0 |

Current JPEG also yields25correct/7unknown/0wrong; every individual acceptance
outcome agrees with current native PNG. Preserve original display and per-call
confidence/sources; unknown is never filled from neighbouring frames. Current
acquisition/decode/integrity work takes428.182s. The64paired static reader calls
and terminal checks take8.415s. They are separate staged timings, not end-to-end
E2E wall time or a speed benchmark against older narrower processing.

## Physical cross-component leak found

The timer training tick1059881 =69.002669secalso appears as a purchase-phase
control in the previous native phase report. Encoded JPEG and native pixel hashes
can differ while referring to the same physical frame; comparing hashes alone
would miss this leak.

Retain all13phase diagnostic controls and their results. For a future joint
qualification bundle, that one source cannot belong to the negative split while
remaining timer training. Twelve phase controls remain jointly eligible, subject
to the rest of the combined split audit. The individual phase component-support
dictionary must not be installed unchanged in a joint bundle. No evaluation
assertion or existing diagnostic input is removed.

## Qualification limits and next action

The prior timer negatives are eight alternate score-/HP-adjacent source fields,
not natural timer-absent observations at the production timer ROI. Four known
misread controls are readable-positive error cases, not absence negatives.
Do not convert either population into unmeasured full-frame negative accuracy.
Current natural timer-absent ROI qualification remains unverified; no real global
sidecar or formal boundary is created by this check.

A separately frozen next review plan keeps complete native cadence in
R1[3.9,4.5],R2[111.2,111.8],active[8,8.5],menu[85,85.5]and
spectator[160,160.5]. None contains a timer-training tick. Entire temporal contexts
must stay within the correct split; do not compare only boundary endpoints or
pretend repeated frames are independent event episodes. These windows are
existing source development contexts, not newly blind lifecycle holdout. Their
labels and predictions have not been generated in this investigation.

No production changes, extra unit runs or full E2E: preceding2690PASS/6SKIP,
Ruff/mypy remain the last code verification. All82canonical statuses remain
historical23PASS/55FAIL/4NE; Current full/Delta unavailable. Windows is unverified.
The fixed expected-score discrepancy is retained as an evaluator FAIL.

Bindings and exact comparisons:
[lifecycle_timer_current_native.json](../e2e_reports/match_001/lifecycle_timer_current_native.json).
Frozen next sequence plan:
[lifecycle_ui_review_plan.json](../e2e_reports/match_001/lifecycle_ui_review_plan.json).
