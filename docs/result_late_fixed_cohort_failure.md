# Fixed late-result source cohort: qualification failure

## Problem / target

Round end (`GT-R1-ROUND-END` and its count/ordering constraints) still requires
qualified global result evidence and justified time semantics. Check whether the
existing frozen late-result reference actually generalizes before producing a
qualification report or proposing a new reference.

## Protocol / evidence

Before predictions, fix the current unchanged diagnostic profile and source
interval76.35–76.55sec. Every native frame in the interval is processed. A source
exposure inventory excludes known saved native ticks, the frozen reference's
training/holdout/control timestamps, and decoded frame timestamps from historical
raw processing runs. Of12native frames,8are excluded and4remain for review.
The selection uses no predicted value or GT expected value/time/round ID.
It is conservative recorded exposure exclusion, not proof that all historical
exposure is known. All selection input hashes are rechecked before updating the
analysis; the selection-time failure-analysis preimage is retained locally.

Actual RealHudAnalyzer processes four origin frames only for geometry and all12
contiguous source frames. No prefix gap corroborates a boundary. Source code and
profile fingerprints are terminal-verified. Prediction/source assets are saved
before review. The full source contact sheet shows readable `TEAM ACE` on all12
images; review is explicitly post-prediction, not blind.

## Result / competing hypotheses

The frozen selected native images3,5,8,9 each have visible text, but all four
producer outputs abstain. Fixed-ROI, unchanged-mask diagnostics give minimum
three-group NCC0.8559,0.8367,0.8143,0.8160respectively. At least one group fails
the unchanged0.90threshold on every image. No lower threshold, text repair,
new reference, missing-group substitution or inferred round end is used.

The source word is present, so absence of the word cannot explain these
abstentions. Possible causes include mask/background dependence and appearance
variation; neither is yet established as the sole cause. Shape/contrast/group
rejection details are retained in the report. The original training images must
be used to investigate a replacement representation; fitting masks on this
failed cohort and calling it independent qualification would be invalid.

The component positive-support gate is not satisfied: selected correct0,
unknown4,wrong0. This is a concrete recognition/generalization failure, not just
missing qualification paperwork. The entire12frame cohort has0accepted results,
0accepted timers and5accepted score pairs. Those acceptance counts do not prove
numeric correctness. Raw phase presence is0; no phase absence is inferred.

## Previous / Current / Delta

This is a new fixed workload with no comparable previous runtime or correctness
counts. Earlier29accepted results in a different108frame interval must not be
compared as an accuracy delta. Producer runtime54.056405sec; no speedup claim.
Released events0→0; canonical baseline23PASS/55FAIL/4NE, new Current/Delta unknown.
No full E2E, qualification report or profile adoption. All82assertion statuses
remain unchanged. Production/source/schema code is unchanged this turn; prior
61relatedtests/Ruff/mypy results still apply, and data-only diagnostics need no
new implementation test.

## Remaining blocker / next action

Reassess result-reference mask/representation using the original distinct training
images, with unchanged NCC/minimum support and a separate newly reserved source
cohort for any next validation. Keep these12images as exposed development evidence.
Do not treat three distinct source images as three independent round episodes,
and do not require an extra video merely to satisfy an invented episode count.
Reader generalization, independent temporal qualification, actual active lifecycle
and end timestamp semantics remain separate gates.

Artifacts under `e2e_reports/match_001`:
`frozen_result_late_native_cohort.json`, `result_late_fixed_native_predictions.json`
and `result_late_fixed_native_review.json`. Source PNGs remain local under
`outputs/recognition-investigation/result-late-fixed-native-cohort`.
