# Partial rounds and independently evidenced starts

## Current task policy (2026-10-09)

The latest recording policy is authoritative: `match_001` is an Outplayed-cut
clip and remains a discontinuity/partial-round/negative-safety regression source.
Main real-video lifecycle qualification waits for the new unedited full match
`match_002` and its independent validation preparation. The video was received
on 2026-10-09 with user confirmation of no editing; source intake is complete,
but pack/manifest registration and lifecycle evaluation remain pending. See
[recording intake and validation plan](round_lifecycle_recording_plan.md).
Neither dataset is deleted or substituted; no match_001-specific OCR/threshold
optimization is undertaken while awaiting the new source.

The user's revised instruction supersedes the earlier requirement to prove a
complete R1 end using the current recording. The prior completion-blocker
section in `round_lifecycle_qualification.md` describes the old task scope; it
is not a reason to stop independently safe R2 work. OCR candidate iteration is
deprioritized. Thresholds, confidence policies, schemas, Validation Pack,
assertions and negative safety contracts remain unchanged.

## Runtime contract

- Missing R1 end evidence produces **no round_end** and no inferred win/loss.
  The observed fragment is retained as an incomplete package.
- A new source segment clears the prior lifecycle, not the recorded raw facts.
  Independently confirmed preparation, timer transition and continuity can
  establish a later start without a prior end event. No R2 timestamp or ID is
  injected into recognition.
- A missing prior end alone is not permission to accept a new start in an
  already active continuous round. A source reset and fresh corroboration, or
  another independently qualified lifecycle route, remain necessary.
- An incomplete package's time-range end is a **scope boundary**, not evidence
  that gameplay ended there. Existing schema expresses incomplete context
  through zero timeline completeness and unknown round result; do not add
  non-schema fields or fabricate an end event.
- Preparation belongs to the independently detected upcoming start. Boundary
  events, observations, facts and snapshots retain native time-based package
  association through trace. A package ID is not a GT label or proof of a round.
- No score, timer, result, phase or ownership evidence is carried across a
  discontinuity to confirm a boundary.

## Implemented safety correction

Baseline: merged main `03bfcbf945fbf3d7b04c54d80b3c5ff103475db0`.
RoundPackageBuilder previously recognized only integer continuity segments,
while GlobalRoundLifecycle emits opaque string segment tokens. Ignoring the
string tokens could join a start/end from different source segments into a
complete package. Both token forms are now retained without coercion; integer
0 and string "0" are not the same segment. Empty strings remain unavailable.
No additional trust, confidence or lifecycle emission is granted by this fix.

Existing lifecycle reset and partial-window logic are reused, not duplicated.
Synthetic tests now exercise R1 start, source interruption, fresh independently
qualified R2 preparation/start and **no ends**, through the native event builder,
Schema-validated packages and trace adapter. They require two distinct packages,
unknown results, incomplete context, system actors and unchanged unknown player
identity. Removing preparation, weakening timer/continuity or removing the
fresh-source reset suppresses the second start. These fixtures are not real
qualification reports or a claim that this recording already yields R2.

## Separate current outcomes and remaining work

| Category | Current item | Treatment |
| --- | --- | --- |
| Source-limited validation | R1 complete end across reviewed discontinuity | Not a mandatory task completion gate for this recording; retain partial, never join evidence. |
| Implemented contract, synthetically verified | Independent fresh-segment R2 start without R1 end | Preserve existing gates and native/package/trace association. |
| Implementation defect | String continuity tokens ignored by package builder | Fixed and regression-tested. |
| Implementation/qualification incomplete | Real scene-only continuity and positive UI-transition producer | Main's downstream contract exists, but source analyzer still does not produce qualified inputs; implement/qualify separately. |
| Observation ambiguity | R2's occlusion and interrupted preparatory context | Remains unknown; not automatically assigned to footage absence or solved by partial packages. |
| Unmeasured current result | Full canonical real-video run after these changes | No current PASS/FAIL/NE or real R2-success claim yet. |

Do not reclassify official evaluator outputs to make this distinction. In
particular, GT-R1-ROUND-END remains governed by the unchanged Validation Pack:
an unmet assertion can still be FAIL even though that outcome is now outside
the task's mandatory acceptance criteria. Source limitations versus producer
defects belong in an accompanying diagnostic explanation, not altered
assertions, evaluation thresholds or invented NOT_EVALUATED values.

## Additional recording and reproducible validation

For complete-end qualification, supply an unedited sequence containing the
purchase-phase end, active round, actual result/score transition and following
purchase/start, with no removed frames/time. Provide separate positive and
negative sequences for qualification, including player death while the round
continues, spectator/remote/menu/map views, natural scene cuts, occlusion and
duplicate/frozen frames. Record resolution, HUD scale and calibration profile
hashes. Original videos, templates and model assets stay local outside Git.

Use the existing Windows/Pi E2E runner and ordinary explicit profile/map
settings described in WINDOWS_E2E.md and RASPBERRY_PI_E2E.md; do not modify
the current Validation Pack to fit a new recording. A new source needs its own
independently authored validation dataset and hashes. Keep training, withheld
holdout and negative controls disjoint; freeze the method before reviewing
holdout. Preserve source/code/profile fingerprints, source PTS, raw events,
packages, trace and the canonical evaluator result. Compare like populations.

Next priority is source-independent safety regression and recording intake
preparation, not another result-OCR variant. Real start/end qualification waits
for match_002; partial-package and independent-start implementation does not.

## Verification for this change

- Focused lifecycle, package-boundary, source-continuity and qualified UI-route
  tests: **169 PASS**.
- Full Mac suite: **1675 PASS / 5 FAIL / 5 SKIP**, 158.57 seconds. Local JUnit:
  `outputs/round-lifecycle/pytest-partial-independent-20261009.xml`.
- The five failures are one macOS POSIX path-alias case and four spectator-icon
  cases. All five reproduce on an isolated archive with tree
  `8d243043be0e8552817d482d59c0bb9b2373c799`, exactly matching baseline main
  `03bfcbf` (affected subset: 76 PASS / 5 FAIL / 1 SKIP). None is changed here.
- Ruff and mypy (102 source files) pass; diff check passes.
- Windows execution, Linux shutdown behavior, real-source R2 acceptance and
  canonical E2E improvements are **not** verified by these tests.
