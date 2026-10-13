# match_002 E2E qualification

This public summary excludes private GT timestamps, annotation contents, approval
quotes, source paths and real images. The detailed historical record remains in
the ignored local review directory. A synthetic oracle is not real-video proof.

## Confirmed artifacts

- Source SHA: `55d909c2d6a5f38575d1cb6c249ddfa7e2a48b96535841317adcae704c6f63b6`.
- Metadata: 2214.272 s, 1920x1080, 60 fps, 3 original audio tracks.
- Unedited recording declared; a capture pause does not certify observable
  gameplay continuity. Development/evaluation partition is frozen privately.
- Independent reviews cover 23 boundary pairs, score-derived Round numbers,
  five source-state cores and three scoped continuity intervals.
- One approximate declared end uses the existing time-bounded count contract,
  not fabricated native onset/last-absent evidence. A corrected special-view
  label remains evaluation-only. Exact score-update times and unreviewed
  ownership/state/continuity remain unannotated.
- The private fixture has 141 unchanged source images, rational packet-PTS
  bindings, 45 points, 3 positive states, 47 counts and 28 negatives. Independent
  approval-to-GT reproduction and physical source metadata were verified.
- Twenty-four private provenance inputs and the freezer recipe were archived.
  No GT is consumed by a production recognizer. No private Pack/images are in Git.

Initial fixture: `outputs/match_002/validation_pack_v1`.
Registry: `datasets/manifests/match_002.json`.
Initial Pack fingerprint: `b26b5fc268f8dee0c45da2dfacfc43d815428a9ca08c5bf83ef4a5535545fa7d`.
Assertions fingerprint: `9caae72ed8fb26bd88d230a729640fda8e3811554608b12c5629d17f36799938`.
Formal fixture completion means independent evaluation fixture only, not runtime
qualification. Private artifacts must be supplied separately on another machine.
Verifier compatibility revision: private `validation_pack_v2`, fingerprint
`6232818ab3dc0fd070899497dde806b88c844b7ee7ff0dfbaac17cd05108df5d`.
Original GT/assertions/framework/images and the original Pack remain unchanged;
only the verification-tool fingerprint/compatibility revision changed.
Registration-only preflight exited 0 without Analyzer/Evaluator or shared export;
its source/Pack/assertions fingerprints matched the unchanged manifest Schema.

## Evaluation contracts and tests

The original v3 Schemas, compiler, thresholds and negative semantics are retained.
The original match_001 GT, source, Pack and historical verdicts are unchanged.
The human-approved match_002 confidence policy v1 validates only the native
snapshot.source_confidence dictionary: known keys, finite numeric leaves in
[0,1], additionalProperties=false. Empty/sparse maps confer no identity. No
dictionary is dropped, averaged or modified; other confidence checks are intact.
Upstream's additive Practical Mode Schema leaves this dictionary definition
unchanged. Compatibility accepts only the exact original/current native Schema
and the fixed v1 dictionary-definition fingerprint, not arbitrary Schema changes.

The synthetic evaluator oracle satisfies 46 boundaries. Each boundary rejects
deletion, duplication, wrong Round and a +10-second shift. All 65 prohibited
values yield their specific negative failure; all three positive states reject
deletion. Empty outputs and ineffective evaluators cannot pass these controls.
These are evaluator-sensitivity checks, not production recognizer accuracy.

Snapshot fusion preserves actual HUD source PTS; current Visual/Map-only snapshots
cannot inherit stale HUD fields or owner identity. Same-PTS Trace association,
multiple-Round membership and downstream facts have synthetic regression tests.
Before the latest upstream merge: targeted suite 125 passed; geometry tests
32 passed. After integration: focused strict/practical/builder/policy tests
102 passed; Ruff and mypy (130 source files) passed. Full post-merge pytest:
3515 passed, 4 failed, 5 skipped in 277.80 seconds. The failures are the same four
spectator fixture cases recorded previously and are not claimed resolved.
Isolated origin/main (`1191543`) reproduces exactly these four failures: 46 passed,
4 failed in the two spectator test modules. Baseline imports were confirmed to
come from the isolated main source tree; these are not new branch regressions.
No new remote CI pass is asserted.

## Geometry candidate: not adopted

The human authorized candidate construction and independent qualification,
not production adoption. NCC >=0.90, three anchors and identity separation
remain fixed. No GT/evaluation holdout is used to select references or masks.
The fixed development plan contains 30 training and 30 separate validation
frames, at least 10 seconds apart between roles, excluding prior geometry samples.
Training-derived edge masks/assets are frozen before validation is extracted.
The isolated candidate contains no identity signals or HUD readers.

Candidate v1: **3/30 fresh geometry successes**; known-invalid large-shift,
resolution-mismatch and letterbox transforms of real source images all reject.
Source/config/assets remained unchanged. Transformed controls are not labelled
unmodified real-video negatives. Independent geometry labels and genuine negative
qualification remain incomplete. Temporal stability alone does not establish
that mask pixels exclude digits or state-dependent icons. Structural mask review
is therefore still required. The candidate is not installed in app settings.

## Remaining goal requirements

- Independently qualify static geometry, positive/negative source controls and
  global lifecycle evidence before any separate adoption decision.
- Strict positive lifecycle Full E2E remains **unproven**. Upstream Practical
  Mode is an explicit provisional pathway, not a replacement for strict safety.
- Preserve frozen GT/assertions and document verifier/Pack revisions explicitly.
- Run qualified targeted, fixed-sampled and native full source analysis; verify
  Event/Snapshot/Fact Round affiliation, actors, provenance and discontinuities.
- Measure true/false/missing boundaries, duplicates, negative violations,
  UNKNOWN/UNSCORED, execution time/memory; do not call unannotated intervals GT
  negatives or substitute synthetic results for real-video measurements.
- Verify match_001 safety regression and latest-main CI. Distinguish source,
  recognizer, qualification, Package, Trace and evaluator failures.

No real-video precision/recall, qualified positive Full E2E or completed goal is
asserted here. Private detailed evidence is retained locally, not published.

## Follow-up candidate rejection and CI diagnosis

Candidate v1 structure review found stable numeric glyphs in its masks; it is
rejected rather than adopted. Candidate v2 excludes configured numeric fields,
anchor interiors and dynamic roster/score/spike subregions. Fresh, disjoint
development sampling produced 28 training and 21 validation frames. Geometry
accepted 6/21 validation frames, and the three source-transform controls rejected.
However, 63 single-anchor ablation challenges exposed 16 false HP anchor matches
after the actual HP ROI was erased. All 16 occur in the 21 HP-removal cases;
timer/ability removals did not falsely match. The tiny HP line mask is therefore
not sufficient qualified geometry. Candidate v2 is rejected too, with no runtime
adoption or threshold change. These are counterfactual source-derived controls,
not unmodified real-video GT. References were not altered by the challenge.

The v2 frozen plan's period label incorrectly says 20 seconds; its explicit
sampling list uses the 8-second temporal-split lattice. That metadata and
post-exclusion contrast/ratio accounting are corrected for future outputs, not
silently rewritten into the original artifact. The observed rejection is valid
independently of the label because exact sampled frame identities are frozen.

Geometry/content-exclusion/challenge regressions: 42 passed. The new challenge
fixture initially lacked the required coordinate-system declaration; it was
corrected without weakening production validation or negative expectations.
Ruff and mypy (130 source files) passed.

For main commit `8e87c57`, Basic CI completed successfully. Windows verification
completed with 23 pytest failures, 3490 passes, 11 skips, 86% coverage. Failures
were test-side default-encoding reads of UTF-8 JSON and an illegal Windows test
filename, not the Mac-only four spectator failures. Reads now explicitly use
UTF-8; the on-disk filename uses legal Unicode/reserved-URI characters, while a
separate filesystem-free test preserves quote/angle-bracket URI coverage. No
expectation, threshold or CI skip was relaxed. Affected Mac regressions: 56
passed; actual Windows verification of the fix remains pending.

## Candidate v3: independently reviewed, not adopted

The training-only HP enclosure-boundary experiment excludes numeric interiors
and retains both sides of structural outlines for the unchanged raw NCC matcher.
It reuses the frozen 28 training images, not earlier validation images. A new
fixed sampling phase, excluding prior samples, supplies 24 validation frames.
Assets are frozen before validation; identity signals/readers remain absent.
The candidate accepts fresh geometry in only **3/24** validation frames.
All **72** single-anchor ablation challenges reject the erased anchor; these
counterfactual controls do not substitute for unmodified real-video negatives.

An independent blind human review confirms the mask's fixed-UI scope and the
three configured structures' visibility/alignment in all 24 source images.
Approval is bound privately to the review, source images and frozen candidate
fingerprints. It does not approve ownership, lifecycle timing, continuity or
production adoption. No thresholds, original fixture or runtime policy changed.
The low fresh-geometry acceptance remains a recognizer limitation, not evidence
that the other reviewed frames lack HUD structures. Negative qualification and
strict positive lifecycle Full E2E remain incomplete.

Candidate report SHA:
`ef3e51e1912e0d993f78037b0a41277dbaac460510321aa39f4e1efc317792f8`.
Ablation report SHA:
`feba28285068c370dc6ca791af7ab2172459e5a21173041cd7afe40270a0dacf`.
Candidate/enclosure/challenge/blind-review regressions: 49 passed; Ruff,
mypy (130 source files) and diff checks passed. These are not full-suite or
real-video lifecycle PASS claims.

For main commit `9f870b7`, both Basic CI and Windows verification subsequently
completed successfully. This confirms the CI test-harness fixes, not adoption
or real-video qualification of this local geometry candidate.

The reviewed-measurement CLI binds the human approval, blind receipt, frozen
assets and source image inventory by hash and recomputes runtime measurements.
It never fits assets, changes thresholds, imports lifecycle GT or approves a
profile. Missing runtime scores remain unavailable, not fabricated zero scores.
The 24 sampled frames contain 22 unique source images; repeated images are not
counted as additional independent visual conditions.

Per-anchor acceptance is timer 9/24, HP/armor 16/24, abilities 21/24. The timer's
raw NCC median is 0.843 whereas its descriptive edge similarity median is
0.931. This is evidence of a pixel/structure mismatch in some cases, not proof
of a safe replacement matcher. The edge metric has no acceptance threshold and
cannot qualify geometry. A training-only reference-medoid comparison did not
justify a new candidate: timer support changed 13 to 14, HP support worsened
18 to 13, and ability support remained 22. No validation pixel selected a
reference and no new candidate was promoted from these measurements.

Reviewed-measurement receipt SHA:
`9fcb36da7d3f00ab1c114861e7c5d668d969ec78886f9460e3dd6bb51ca7eba0`.
Expanded diagnostic/geometry regressions: 62 passed; Ruff, mypy (130 source
files), and diff checks passed. An initial synthetic case exposed missing
runtime score handling; the implementation now reports unavailable explicitly
instead of assuming every anchor has a score. No existing test was weakened.

## Latest-main integration and failed baseline attempt

Upstream main `c11ec6d` was inspected and merged without discarding the local
geometry work. Its native calibration-prefix/UI-measurement extensions remain
opt-in and unqualified; they do not convert geometry into player identity.
The private v2 evaluation fixture still verifies against the integrated code.
Related native/UI/report/confidence regressions: 183 passed. Ruff and mypy
(131 source files) passed. Actual Basic CI for this main SHA succeeded;
Windows verification subsequently completed successfully too. These CI outcomes
do not establish match_002 real-video lifecycle accuracy.

The complete Mac suite on exact main recorded 3628 passed, 5 failed, 5 skipped
in 276.77 seconds. Four failures are the previously reproduced spectator
fixtures. The fifth settings-only runner test collided with the simultaneously
running real E2E repository lock, before its injected services were called.
Its lock directory now uses the test's temporary repository root; settings
assertions and production lock behavior remain unchanged. Map-runner and actual
cross-process lock exclusion/release regressions: 14 passed while the real
baseline still held its own lock. The full suite has not been rerun after this
test-isolation correction, so no new full-suite PASS is claimed.

A fresh full baseline was started from exact main `c11ec6d` with the original
local profile and the unchanged production sampler. It does not use the local
geometry candidates, expected labels or external AI. This is not an all-native-
frame lifecycle qualification run.

The process terminated with exit 2: `HUD calibration_required:
insufficient_anchors`. It observed 13,287 HUD frames with zero fresh or effective
geometry successes; all 13,287 frames contributed to `insufficient_anchors`.
This is an input-profile/geometry qualification failure, not an independently
demonstrated Visual, Map, Package or Evaluator failure. Those downstream stages
were not reached. The Evaluator was not invoked, and no evaluation report exists.
There are no measured lifecycle accuracy or negative-assertion verdicts to claim.
The runtime summary's returned-result frame_count=0 must not be mistaken for
zero decoded/HUD-observed frames. The empty error trace is not a safety PASS.
Embedded profile-generation diagnostics describe the pre-existing imported
profile, not a fresh reference-training run on this video.

Analyzer wall time: 1971.697 s; orchestration wall time: 1975.636 s. Decode took
720.242 s, HUD geometry/features 1177.420 s, and numeric OCR had zero calls.
A short stack sample identifies Hough-circle processing as a performance
candidate, not a complete time attribution or an excuse to weaken detection.
Post-run source SHA, runtime-code fingerprint, profile/all assets and private
Pack fingerprints all matched their initial bindings. Source, raw output, Trace,
timings and error logs remain local. The generated shared reports contain only
the bounded privacy-filtered failed-run summary and hashes/statistics; no video,
source images, OCR text or private GT are included.

Next: independently finish candidate geometry qualification and run a bounded
development-only candidate probe before any adoption decision or another full
run. Preserve the original profile and baseline. Do not compensate for the
calibration failure by lowering NCC, adding GT-derived boundaries, bypassing
identity/geometry guards or treating unexecuted downstream checks as successful.
