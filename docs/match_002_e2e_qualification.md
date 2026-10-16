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

## Bounded real Analyzer connection of geometry candidate v3

A private point-only CLI replaces only the isolated trial's geometry anchors.
It preserves the base layout and independent signal/reader assets by hash,
rejects geometry-as-identity asset reuse (including renamed identical contents),
keeps existing anchor floors and does not inherit a global qualification file.
It never installs app settings, generates references or runs AI. Human geometry
labels check artifact admission but are not passed into the Analyzer.

The actual `RealHudAnalyzer` processed the same 24 reviewed development source
images with event generation explicitly disabled. All 24 observations passed
the existing HUD Schema. Fresh geometry succeeded 3 times; effective geometry
succeeded 13 times (10 retained), and 11 frames remained geometry-invalid.
All 24 primary states were unknown. Identity reasons: geometry_invalid 11,
spectator_exclusion_unverified 11, competing_view_evidence 1,
structure_evidence_insufficient 1. Timer, both scores, HP and ammo remained null.
The measured Analyzer time was 3.871 s; this excludes source hashing/admission
checks and is not a continuous targeted or full E2E runtime.

Global numeric acquisition has an additional concrete configuration gap:
the base profile has only a HP/armor reader and explicitly empty OCR fallback
ROIs. It has no configured Timer/Score reader. Production `_read_values` is
invoked before live identity classification when geometry is valid, so this
missing acquisition configuration must not be conflated with identity failure.
Do not remove the spectator gate to compensate for absent global readers.
Any future numeric-reader proposal needs separate source/negative qualification;
this probe does not enable a fallback or relax its confidence policy.

Probe receipt SHA:
`5ac944369528b9e7c6e67e80ee307599db3baafd954c39eb67aa4e7f31cf61d7`.
Geometry/probe/review/enclosure/challenge regressions: 23 passed. The probe
rejects incomplete observation coverage and any unexpectedly generated event.
It preserves source/video/base/candidate/review bindings and leaves thresholds,
original profiles and the frozen evaluation fixture unchanged. No formal event,
identity qualification, negative-assertion verdict or production adoption is
claimed from these isolated observations.

A repeat with explicit runtime/probe-code fingerprints and post-run review/
approval integrity checks produced identical observation bytes and counts.
Measured Analyzer time: 3.642 s. Versioned repeat receipt SHA:
`fc75d2be3e27d4726c5c26a77f73d2dae9f8905d700aa55fa9e54bcfd6d8dc06`.
The original receipt remains unchanged. Neither run confers negative or
temporal qualification; further work is needed before production adoption.

## Global numeric acquisition proposals: unqualified

An explicit diagnostic-only `--global-digits` option adds absent Timer/Score
readers with minimum confidence 0.90 and strict timer format. Existing readers
(including stricter ones), fallback policy, independent assets and identity
gates are not replaced. The base profile remains unchanged. Producer-side
diagnostics are captured before value admission and stored only privately.

On the exposed 24 development images, broad-ROI OCR produced zero accepted
Timer/Score values, both before and after state admission. A source crop check
returned `tesseract_no_digits`; simple bright-text binarization alone also did
not meet the unchanged confidence floor. This narrows the acquisition problem
to numeric text isolation, rather than an identity-gate override.

The diagnostic component-row proposal uses configured ROI pixels, bright
connected components, relative size/aspect and row consistency. It rejects
ambiguous rows, blank/frame-only regions, and timers without an observed
two-dot colon. It does not synthesize missing punctuation. No expected digit,
GT timestamp, evaluation Pack or state label enters the proposal. This is a
crop candidate, not proof that its contents are a timer or score.

With `--diagnose-numeric-localization`, these crops are measured strictly
outside the Analyzer. Of 24 images per field, proposed crop counts were Timer
13, ally Score 19, enemy Score 19. OCR confidence>=0.90 plus syntax held in
9, 13 and 16 cases respectively. These are **not correctness counts or
accuracy**, include potentially geometry-invalid points, and are not used to
select an accepted production reader. Runtime observations remain 24 unknowns,
with no admitted global numeric values or events. The known development images
are exposed diagnostics, not a new independent holdout.

Probe receipt SHA:
`2a3d00cc85eefcb2688a908e78302d3b0dbb38b13895ce14f75ea0109641168d`.
A private blind review page shows broad configured ROIs and original images,
not OCR predictions/confidence or proposed crop boxes. All numeric labels
remain unset pending independent review; no review approval is inferred.
Its receipt SHA:
`58419da660cd9c08141fb604c84f23fbc4c11e1edb76d3a3c51d1f46d0808f75`.

Related geometry/numeric/probe/blind-review tests: 84 passed; Ruff, mypy (131
source files), and diff checks passed. Tests preserve stricter existing readers,
reject below-floor/NaN/malformed timer reads, prohibit colon fabrication and
qualification inference, and keep model predictions out of human review.
Next: independent numeric labels and prospective positive/negative source
controls before integrating a qualified numeric reader into the temporal path.
No pipeline contract, original Schema, threshold or production setting changed.

Numeric review ingestion requires an actual explicitly supplied response and
a provenance reference. Its private revision binds the original blind receipt,
reviewed ROI image hashes and exact response bytes. Blank/unanswered cells stay
unreviewed, `unknown` stays distinct from `absent`, and no missing number is
filled from OCR. Whole-batch approval without numeric labels, duplicate/unknown
frame IDs and malformed values are rejected. Existing receipt/label revisions
are never overwritten. Declaring a provenance string is not programmatic proof
of human authorship; the trusted conversation record must separately establish
it. No numeric response has been received or frozen for the real 24-image batch.
These source labels do not approve identity, lifecycle timing, continuity or
production adoption and are never a production recognizer input.
Ingestion/related diagnostics regressions: 103 passed; Ruff, mypy (131 source
files) and diff checks passed. Invalid/non-finite source times and changed
review assets are rejected. All human-label tests use explicitly synthetic
responses and do not constitute a real review or a numeric accuracy result.

## Explicit numeric review comparison (2026-10-14)

The subsequent trusted human response supplied all 24 numeric rows. The earlier
pending-review statements above describe the preceding checkpoint, not current
status. Exact labels and response bytes were frozen privately against the
unchanged blind receipt and reviewed ROI hashes. They authorize numeric
visibility only, not identity, event timing, continuity or production adoption.
The lifecycle GT and formal Validation Pack remain unchanged.

The already frozen component-crop probe was compared without rerunning the
Analyzer or OCR, altering its confidence floor, or selecting a new reader.
Counts are for the 24 exposed development points, not an independent holdout:

| Field | Visible values | Correct reads | Missing | Wrong reads | Absent false accepts |
| --- | ---: | ---: | ---: | ---: | ---: |
| Timer | 16 | 9 | 7 | 0 | 0 |
| Ally score | 22 | 13 | 9 | 0 | 0 |
| Enemy score | 22 | 16 | 6 | 0 | 0 |

Absent correct rejections were 8, 2 and 2 respectively. There were 22 unique
source images; repeated identical images are not independent conditions.
Unique-image missing counts were 5, 7 and 4 respectively. No unknown or
unreviewed labels were silently counted as successful negative controls.

Each field had 3 point-level misses without a crop proposal. Further misses
after crop proposal were Timer 4, ally score 6 and enemy score 3, due to the
unchanged OCR floor or format requirement. This is a diagnostic classification,
not evidence to lower thresholds or repeatedly tune OCR against these labels.

Correct diagnostic reads on geometry-valid points were only 6, 7 and 10.
Geometry-invalid diagnostic reads are reported separately and cannot enter the
production pipeline. Original runtime observations still contain no admitted
global numeric values or events. No continuous lifecycle or full E2E positive
result is established by this point-only comparison.

The comparison CLI verifies exact human response, label/review/probe/raw hashes,
complete per-field inventory and source-image association. It rejects changed
assets, missing/duplicate rows, malformed or below-floor accepted outputs and
conflicting reviews of identical images. Output is counts and hashes only;
source labels, OCR strings, images and timestamps stay private. Next work is
prospectively frozen source/negative qualification before any reader adoption;
the final evaluation holdout must remain outside training or candidate selection.

Numeric comparison and related geometry/review/probe regressions: 124 passed.
Ruff, mypy (131 source files) and `git diff --check` passed. This is the targeted
regression suite, not a new full-suite or real-video lifecycle PASS.

## Prospectively frozen numeric cohort (2026-10-14)

The unchanged numeric proposal was measured on a new fixed development cohort.
Sampling uses a predeclared phase/period and excludes prior unlabelled geometry
training/validation points within 2 seconds. Neither numeric review labels nor
lifecycle GT/Validation Packs determine the sample times. The plan binds source,
runtime/proposal code, original trial layout/profile, assets and prior diagnostic
receipts before decoding. No reference training or profile installation occurs.

Twelve development points were retained, all with unique images and zero hash
overlap against prior candidate training/validation images. No outcome-dependent
sample replacement occurred. Final evaluation holdout was not decoded or used.
The real point Analyzer produced 11 unknown states and 1 buy-menu state, with
event generation explicitly disabled. These are not continuous temporal
observations and cannot establish lifecycle boundaries or source continuity.

Outside the Analyzer, unchanged crop/OCR confidence>=0.90 and syntax conditions
held in Timer 7, ally score 6 and enemy score 10 cases. These remain **proposal
acceptance counts, not correct-read counts** until the new independent source
review is complete. No production numeric admission, adoption or qualification
is inferred. Private source-only review shows broad ROIs/original images and
withholds predictions/confidence/proposed crops. It has no labels or inferred
approvals. If positive or absent-negative coverage is insufficient, further
independent controls remain necessary rather than declaring qualification.

Source SHA, runtime fingerprint, source images and frozen inputs were checked
again after processing. Planning/comparison/geometry/numeric regressions:
136 passed; Ruff, mypy (131 source files), and diff checks passed. This is not
a new full-suite or full-match E2E PASS. The latest fetched main remains the
previous exact baseline commit; no experiment has been installed there.

The independent numeric response for the new cohort remains missing. A later
integrity audit confirmed all twelve decoded points are inside the original
frozen development partition, original receipts/raw bindings are unchanged and
source SHA still matches. No Analyzer or OCR rerun occurred.

Future diagnostic plans use an explicit v2 contract: the source-bound non-GT
partition file is required, the CLI limit must equal its frozen development
end, and its hash is checked before/after processing. Decoder pixel/probe and
Tesseract executable fingerprints are also frozen and checked. Changed source,
partition or toolchain fails before decoding. A v1 plan is not rewritten or
upgraded in place. Current post-run toolchain measurements are not retroactively
claimed as pre-run provenance for the already completed v1 cohort. No production
Schema, recognizer threshold, qualification policy or formal fixture changes.

The existing Mac spectator regression was revalidated separately: 50 passed,
4 failed in the icon/absence/runner modules. The abstract positive icon reports
7 orientation bins against the unchanged required 8, with ambiguous/unknown
output. This explains the shared synthetic fixture failures; it does not prove
a real-video defect or justify weakening the eight-bin contract, changing
expected results or claiming the full suite is green. Production stays unchanged.

Updated partition/planning/numeric/geometry targeted suite: 145 passed; Ruff,
mypy (131 source files), and diff checks passed. The four separately reproduced
spectator failures remain recorded and unresolved; no full-suite PASS is claimed.

## New cohort independent numeric review received (2026-10-14)

The trusted human subsequently supplied all twelve explicit source rows. The
earlier missing-response statements and blocker audit are historical, not
current. New immutable label/response revisions bind the original blind ROI
assets, source hashes and frozen probe receipt. No original receipt, lifecycle
GT, Validation Pack, raw probe output or code/profile was modified to fit labels.
Analyzer and OCR were not rerun; prediction-free review remained independent of
the frozen outputs. Scope remains numeric visibility only, not identity,
event timing, continuity, temporal qualification or production adoption.

| Field | Visible values | Correct reads | Missing | Wrong reads | Absent negatives | Absent false accepts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Timer | 10 | 7 | 3 | 0 | 2 | 0 |
| Ally score | 12 | 6 | 6 | 0 | 0 | 0 |
| Enemy score | 12 | 10 | 2 | 0 | 0 | 0 |

All twelve source images are distinct. Timer's 3 misses and enemy score's 2
misses occur after a crop proposal but fail the unchanged OCR floor/format.
Ally score has 1 no-crop miss and 5 OCR floor/format misses. No thresholds were
relaxed. Zero wrong accepted values is evidence about these reviewed points
only, not general accuracy or precision across a match. The new cohort contains
no absent-score negative; therefore it proves nothing about absent-score false
acceptance. Prior exposed negatives remain separate and are not relabelled as
prospective negatives or merged into a stronger qualification claim.

Geometry-valid point counts contain only Timer 5, ally score 5 and enemy score
8 correct diagnostic reads. Geometry-invalid reads remain outside admissible
production input. All localized results still have passed_to_analyzer=false and
localization_qualified=false. No runtime Round events or actual Package
affiliation were established by this comparison. Broad numeric acquisition,
geometry and continuous temporal qualification remain incomplete.

Remaining qualification must cover actual absent-score source evidence,
continuous start/end evidence and geometry without deriving labels from OCR,
using final evaluation holdout to tune, weakening confidence/negative contracts
or installing an unqualified profile. The response resolves the numeric-review
wait; it does not establish full-match lifecycle success.

The existing `GlobalLifecycleQualification.load` contract requires at least
three distinct training, holdout and negative hashes per component, disjoint
within and across components, at least three reviewed correct holdout cases,
zero wrong holdout cases and zero negative false positives. This new cohort has
only two absent Timer images and no absent Score images, so its source-negative
support alone is insufficient even though accepted values were all correct.
Do not reduce required support or manufacture qualification from these counts.
Broader source/temporal components still require their own reviewed evidence.

Review ingestion/comparison/planning regressions: 63 passed; Ruff, mypy (131
source files), and diff checks passed. This targeted result does not replace
the separately recorded full-suite spectator failures or formal real-video E2E.

## Additional source-negative candidates (2026-10-14)

The unchanged numeric crop/OCR proposal was measured against a new source
cohort intended to find absent-value controls, without assuming that any image
is actually negative. A fixed 5-second development grid was frozen before
decoding, excluding prior geometry samples and the previous numeric cohort
within 2 seconds. Only source/PTS/hash metadata is consumed from prior diagnostic
reports; no review labels, GT timestamps, Validation Pack or OCR predictions
select the source pool. The final evaluation holdout remains untouched.

The frozen pool retained 75 points. A predeclared ranking selects the six lowest
raw grayscale ROI standard deviations per field, deduplicates source images
and freezes selection before invoking numeric OCR. Low contrast is **not** an
absence/unknown-state proof. Human review must supply visible values, absent
or unknown normally; a visible number cannot be relabelled as absent to fill
the negative quota. This is a contrast-selected control cohort, not a random
accuracy/recall estimate or a proxy for diverse real-world negatives.

Thirteen distinct images were selected, with no hash overlap against previous
candidate training/validation or reviewed numeric cohort images. Real point
Analyzer output remained 13 unknowns with event generation disabled. Outside
the Analyzer, unchanged OCR confidence/format conditions held in Timer 4,
ally score 8 and enemy score 9 cases. These are not correctness or false-positive
counts. A prediction-free private review page has no numeric labels yet. No
negative verdict, qualification file, production adoption or lifecycle event
is fabricated from this measurement. If reviewed controls remain insufficient,
do not relax the existing distinct-evidence requirements.

Source, code, profile/assets, partition/toolchain and frozen selection hashes
were verified after processing. Original earlier cohorts and human responses
remain immutable. This diagnostic sampling/ranking extension does not change
production recognition, Schemas, confidence/NCC thresholds, identity gates,
source continuity or the formal evaluation fixture.

Probe receipt SHA:
`76970b2bfcbd7542b0b57482fecb15d2e077cde6ba947315e2dc22fd315c231d`.
Blind receipt SHA:
`285fdcf9421057e801d705c9da5868c06eb34ab5e1646650f137f2e6cff07aa1`.
Planning/numeric/geometry/review targeted regressions: 152 passed; Ruff, mypy
(131 source files) and diff checks passed. No new full-suite or full E2E PASS.

## Source-negative review and diagnostic reader connection (2026-10-14)

The trusted human supplied all 13 explicit source rows. Exact response/label
revisions are private and bound to the original blind source assets. Earlier
pending-review statements describe the preceding checkpoint. Low contrast did
not imply absence: reviewed absence counts are Timer 6, ally score 1 and enemy
score 1, not thirteen negatives per field.

| Field | Visible values | Correct reads | Missing | Wrong reads | Absent false accepts |
| --- | ---: | ---: | ---: | ---: | ---: |
| Timer | 7 | 4 | 3 | 0 | 0 |
| Ally score | 12 | 8 | 4 | 0 | 0 |
| Enemy score | 12 | 9 | 3 | 0 | 0 |

The source includes a fractional Timer display. Review ingestion now preserves
fractional source strings exactly; Decimal comparison never truncates/rounds
them to make integer-reader outputs correct. Production formats, Schemas,
thresholds and original raw outputs remain unchanged. The fractional case was
unlocalized/missing, not accepted or silently counted as absent. No private
source value, label row or timestamp is published here.

A diagnostic-only adapter wraps explicit empty-template numeric proposals and
the existing configured reader, preserving stricter confidence floors and OCR
settings. It rejects strict readers, trained glyphs and inner-ROI overrides;
localization never confers a numeric crosscheck. Missing colon, fractional OCR
output, non-finite/below-floor confidence or missing provenance stays absent.
It is not registered as a production profile kind and never installs settings.

Through the real Analyzer reader-injection entrance, the already frozen twelve
development points yielded normalized values in Timer 5, ally score 5 and enemy
score 8 cases. All 12 observations were Schema-valid, with 11 unknown states
and 1 buy-menu state, unchanged from the original probe. Player ownership
promotions and events were both zero. The thirteen source-control points yielded
Timer 4, ally score 8 and enemy score 9 normalized values, 13 unknown states,
zero ownership promotions and zero events. Direct reader connection works;
this is still unqualified point processing, not continuous lifecycle proof.

The source-control cohort's only absent-score image is geometry-invalid, so
Analyzer-level abstention there cannot independently qualify the Score reader.
Outside-Analyzer localization abstained on that actual image, but one image
still falls below the unchanged distinct-negative support requirement. Prior
exposed/training negatives are not relabelled as prospective controls to fill
the quota. Global components, geometry and temporal/source qualification remain
incomplete; no qualification file, production adoption or full E2E PASS.

Connection receipts:
`8f2d06fee1c0f5da7915f2c588511f1103fefb143d7d289d708c01e06189472f`,
`d79ccebb21491a56850c058da23659a2f980b3b5bcf97f379ca5d7cad0d4fbe4`.
Review/planning/adapter/probe targeted regressions: 108 passed. Ruff, mypy (131
source files) and diff checks passed. Existing full-suite limitations remain.

## Remaining fixed-pool score-presence review (2026-10-14)

To investigate insufficient absent-score support without tuning OCR or decoding
another cohort, the remaining images of the already frozen 75-point development
pool were prepared for source-only presence review. All thirteen previously
selected/reviewed source hashes are excluded without reading their labels.
Exact duplicate images are deduplicated, leaving 61 distinct unreviewed images.
No OCR, Analyzer, source sampling, GT input or reference generation was rerun.

The private gallery shows only broad configured ally/enemy score ROIs and
original-image links. It requests only frame IDs with actually absent scores,
not full numeric transcription. Unreadable is not absent; omitted responses stay
unreviewed and cannot become positive or negative labels. A source-only receipt
binds the original frozen selection, parent probe, layout and all reviewed
image/ROI hashes. It does not bind fabricated model results for unmeasured points,
infer negative support or authorize production/temporal/identity behavior.

Presence receipt SHA:
`c41f7dd51904503bb7484df0a5e43326d52fe6f509e8942de32709f430e04b08`.
If this pool does not contain enough independently reviewed absent-score
evidence, retain the qualification failure rather than sampling nearby copies
of a black screen merely to satisfy the minimum count. Source diversity and
real numeric-reader behavior remain separate from geometry-gated abstention.

Presence/adapter/numeric/planning/probe targeted regressions: 112 passed. Ruff,
mypy (131 source files) and diff checks passed; full-match lifecycle is incomplete.

## Sparse presence response and fixed-reader controls (2026-10-14)

The human subsequently identified two remaining-gallery images with both scores
absent. Only those explicit cells are frozen; the other 59 images remain
unreviewed and Timer labels are not inferred. The private revision binds the
exact response, trusted conversation reference, original source/ROI hashes
and receipt. Original reviews, earlier blocker audits and outputs are unchanged.

The unchanged diagnostic adapter was measured on the two reviewed source images,
outside the Analyzer and without native geometry admission. Both scores were
rejected on both images: 2 reviewed controls and 0 false positives per side.
Original profile/assets, numeric localization code and decoder/Tesseract
fingerprints were checked against the source pool's frozen plan before measuring
and again after measuring. The test receives only actual image pixels; expected
absence labels and review Frame IDs do not enter the reader.

Together with the independently reviewed absent-score image in the preceding
source-control cohort, each score now has three distinct absent-source hashes
with zero false accepted values. Hash uniqueness was verified, not achieved by
copying images or counting unreviewed frames. This resolves the specific missing
source-negative support count; it is **not full lifecycle/profile qualification**.
Source diversity/cross-match generalization, geometry, temporal components,
native factory integration and actual Round/Package affiliation remain separate
requirements. No qualification file, production setting or Schema is changed.

Sparse review ingestion rejects ambiguous, unknown/duplicate/conflicting IDs and
changed assets; unknown or a no-matches declaration cannot manufacture negative
labels. Tests exercise an actual false-positive result and verify that it is
reported, not masked by the always-unqualified diagnostic status. Public test
examples use synthetic fractional values rather than private reviewed values.

Integrity-bound control receipt SHA:
`ac21151be5b1ab2ce1174a52402c2a37986854ec8ee4d6b3ef945351e382f283`.
Sparse-review/control/adapter/numeric/planning/probe targeted regressions:
127 passed. Ruff, mypy (131 source files) and diff checks passed. The formal
full-match lifecycle outcome remains unproven; prior full-suite failures remain.

## Explicit native numeric-region reader (2026-10-14)

The frozen pixel-only component-row kernel now has an opt-in native reader:
`numeric_region_locator: "bright_components_v1"`. It is allowed only on explicitly
configured empty-template `digits` readers for the three global numeric ROIs,
with their original timer/integer format. No shipped profile or app setting is
changed. Existing profiles without this field keep the original reader path.
Invalid explicit locator, format, templates, subregion or confidence floor fails
closed instead of allowing legacy OCR fallback. The existing configured floor
is preserved and cannot fall below 0.90. Missing colon pixels, ambiguity,
fractional timers, invalid or missing value provenance and low confidence are
not repaired. Localization never creates an independent crosscheck.

The private connection probe supports `--native`: it clones the existing
unqualified trial profile locally, preserves geometry and identity assets,
and uses the real Analyzer constructor without injected readers. It binds the
new runtime/profile fingerprints separately from historical frozen-cohort
fingerprints; old receipts and outputs are not overwritten. Both original and
generated profile/assets, source video and runtime fingerprints are checked
before/after processing. No qualification file, GT, expected numeric values,
event synthesis or application settings enter this path.

On the twelve-image fixed cohort, normalized Timer/ally/enemy values were
obtained on 5/5/8 images; on the thirteen-image source-control cohort, counts
were 4/8/9. All 25 observations match the prior diagnostic connection in values,
confidence, state, geometry and quality, except for the explicit localization
source tag. Both routes produce zero ownership promotions and zero events.
The source remains unchanged. This verifies native factory connectivity only,
not continuous lifecycle, profile qualification or full-match E2E success.

Native-reader/profile-cloning, existing template behavior, lifecycle safety,
source-negative ingestion and numeric-review regressions: 224 passed. Ruff,
mypy (132 source files) and `git diff --check` passed. Historical full-suite
limitations remain; the full suite was not rerun at this checkpoint. Geometry,
identity and temporal qualification remain separate unfinished requirements.

## Continuous native development input gates (2026-10-14)

Fresh production native-window decoding measured three bounded development
windows around the first start, next start and first result. Every window has
85 distinct physical source rasters, exact integer-PTS cadence, one independent
decoder epoch and terminal source/profile/code checks. No references, expected
values, injected geometry, lifecycle proofs or GT enter recognition. Windows
are not spliced or used to claim a complete Round or source-wide continuity.
The held evaluation interval is not decoded or used for this experiment.

| Development window | Fresh geometry | Effective geometry | Timer accepted | Both scores accepted | Released events |
| --- | ---: | ---: | ---: | ---: | ---: |
| First start | 4/85 | 56/85 | 42/85 | 33/85 | 0 |
| Next start | 7/85 | 31/85 | 30/85 | 20/85 | 0 |
| First result | 15/85 | 85/85 | 77/85 | 50/85 | 0 |

All states remain unknown. Counts above are acquisition, **not reviewed numeric
accuracy or lifecycle recall**. Native global projection releases no owned
values. These runs have no loaded qualification, no configured semantic purchase
or result references, and no released events. Thus the first-result failure is
not attributable to invalid geometry in this bounded window. Missing semantic
inputs, geometry acquisition failures and identity insufficiency are separate
gates; actor=system cannot bypass them or create player ownership. Runtime was
44.761 / 37.018 / 54.634 seconds respectively. Peak RSS/storage was not measured.

Private raw report hashes (in the same order):

- `dccb0058eb823d382c0c0f08f98c5923564683bc73821bb7a87c05250ccc6d37`
- `40b831566dc1f754b2b5b970727429cba3a7097670a9b29dbcc7da35291d5688`
- `b4093af3266b9805de49c69bfaf4429d4bb29136fefa43a1a7912f0fe62c71b4`

The point-trial builder replaced all base geometry anchors with the three
candidate anchors, dropping the original masked top-match-bar anchor. An
explicit `--retain-base-geometry` experiment now preserves missing masked base
anchors, original assets and NCC >=0.90 without replacing candidate anchors,
changing the three-anchor condition, reusing geometry for identity or inheriting
qualification. Original assets remain unchanged; the retained anchor is not
independently source-reviewed for this new recording. Missing masks/assets,
lower floors and geometry/identity asset reuse reject the experiment.

On exactly the same first-start rasters/PTS, the original top-match-bar anchor
accepted 0/85 (NCC min/median/max 0.265/0.277/0.372). All 85 observations remained
identical to the three-anchor trial, including the 56 effective geometries and
42 accepted timers. Therefore merely retaining this old anchor is **not an
improvement** and does not justify adoption or lowered NCC. This counterfactual
took 45.466 seconds; raw SHA:
`b065739f9d514b53ee7cf55196d38e6f0bccd07ced445b771e28d3d63cba62f1`.

Next work must supply independently reviewed, source-supported purchase/result
references and temporal qualification, while separately resolving geometry
coverage. Do not repeat the full baseline with the same missing inputs or
convert accepted numeric transitions into Round events. None of these bounded
measurements is a Full E2E, negative-safety PASS or production profile release.
Related native/geometry/numeric/lifecycle regressions: 198 passed; Ruff, mypy
(132 production files) and diff checks pass. Full-suite limitations remain.

## Unlabeled banner-reference discovery (2026-10-14)

Missing purchase/result references are now investigated using the existing
fixed development image pool, without decoding a new cohort, reading GT/labels,
or selecting by expected timestamps. Previously selected numeric-review parents
and two separately reserved score-control hashes are excluded. Exact duplicate
parents are deduplicated. Remaining source hashes split deterministically into
30 training and 30 held images; the final evaluation holdout is not accessed.

`scripts/diagnostics/discover_banner_references.py` derives bright text-row
proposals from training pixels inside the configured banner ROIs. Foreground
neighbourhood masks and three separated support groups are checked by the
existing `SemanticTextReference`, including NCC >=0.90, contrast/support floors
and three distinct training parents. Selection/ranking uses training support
only. Held images measure frozen candidates and cannot change their masks,
reference bytes, boxes or selection. No OCR or semantic label enters discovery.
All source inputs, candidates, review crops, originating reference-parent hashes
and the review page are bound in a new private receipt.

Three candidate variants were found per configured ROI. Their training support
is 5/4/4, held acceptance 2/1/1. These are repeated shapes, not reviewed correct
phase/result classifications. Both ROIs discover the same purchase-like text
family: an end-ROI proposal is **not** evidence of a round result. No result
reference has been established. ROI names cannot supply semantics. The current
four-component row proposal also does not cover every short English caption;
that diagnostic coverage limitation must not become an absence assertion.

The three reference variants bind three distinct training parents. Human
transcription of those reference images/source parents is requested separately
from lifecycle GT. Semantic labels remain null and no template sidecar,
qualification report, application setting or event is generated. Even an
approved reference transcription would not supply missing held/negative/event-
level qualification or justify production adoption. Multiple same-match frames
must not be counted as independent temporal episodes or cross-match evidence.

Latest private candidate report SHA:
`60d4b9882b65b63473e2e8a7c8816b5610f4029ca2352e7b65b65eb64f42e9ae`.
Review-page SHA:
`499ebe273cf3a35b4465739ca9d6c942061dc57f5c2abbe5b9465a0e8bbbdd17`.
Receipt revisions added source/review bindings only; reference/mask bytes,
training selection and held predictions are identical to the first run.
The fixed development images are exposed diagnostic/regression evidence, not
new blind temporal qualification or a full-E2E improvement.

Tests verify that held-image replacement cannot change training candidates,
blank/background nonmatches cannot imply semantics, reserved/previously
reviewed parents and evaluation-holdout frames cannot enter training, modified
hashes reject before output, and discovery cannot write a configured profile or
qualification. Related discovery/semantic/native/geometry/lifecycle modules:
144 passed. Ruff, mypy (132 production files) and diff checks pass. All existing
thresholds, Schemas, canonical Packs and production recognizers remain unchanged
in this checkpoint; full-match lifecycle is still incomplete.

## Short-caption proposal coverage and pending-review integrity (2026-10-14)

The four-component discovery proposer cannot represent every three-character
caption. Add an explicit diagnostic-only three-component option, leaving the
default four-component proposer unchanged. This changes candidate enumeration,
not the native recognizer, grouped NCC >=0.90, three independent support groups,
contrast requirements, three distinct training parents, semantic labels or
qualification/adoption. Synthetic three-component text becomes a proposal;
two-component text and insufficient training support still reject.

On the same frozen development pool, the explicit option produces the same
reference/mask/group bytes, training support sets and held predictions as the
earlier candidates. Both configured ROIs have 7 training row proposals: 2 fail
the existing training-support requirement, 5 supported proposals reduce to 3
support clusters. Held acceptance remains 2/1/1. No new result-reference support
or actual lifecycle gain is established. Do not continue changing this fixed
cohort's proposal thresholds merely to create a result candidate. The observed
shape counts cannot establish which unreviewed source frames contain a result.

The new proposal diagnostics distinguish enumeration, rejected support, accepted
reference proposals, support clusters and returned candidates. They do not
classify absent purchase/result UI or infer boundaries. Private new receipt SHA:
`3e382329c79f5f56fd282dcab85419d62198a32304b590fc6b7879f476d402e5`.

The earlier pending human-review receipt/page, every source and review crop,
and every reference/mask/group hash still match. The original generator bytes
were separately verified against Git commit `5ba3065`; the modified current
generator is not presented as the historical implementation. The previously
requested gallery and its three reference IDs remain valid; no response or
semantic approval has been received or fabricated. No rereview is requested.

Related discovery/semantic/geometry/native/lifecycle tests: 150 passed. Ruff,
mypy (132 production files) and diff checks pass. Source/GT/Pack and production
code remain unchanged. Next distinguish missing representative training support
from unreviewed semantics, using frozen source-only evidence rather than GT-
selected frames or another full run with unqualified references.

## Additional fixed source-only development pool (2026-10-14)

Instead of continuing to fit the sparse exposed pool, freeze a separate sampling
plan before source capture: phase1.375 seconds, cadence3 seconds, within the
existing development partition, excluding points within0.5 seconds of prior
geometry/numeric sampling metadata. Only source sampling/hash fields are read;
GT, expected state, candidate matching and evaluation outcomes cannot select
the new times. The final evaluation holdout is not accessed. This is additional
development input, not a new independent temporal holdout or validation Pack.
This denser source-collection radius does not replace the earlier two-second
prospective qualification exclusion. Of179 requests,116 fall within that prior
two-second neighbourhood and63 outside it. Neither all179 images nor their
alternating held split can be promoted to independent qualification cases merely
because their encoded hashes differ. The existing qualification/safety gates
remain unchanged; this pool is for development reference discovery only.

`scripts/diagnostics/capture_unlabeled_banner_pool.py` separates plan freezing
from capture, limits requests to256, rejects source/decoder/code/partition drift,
preserves source resolution and actual sampled PTS, and reports duplicate/previous
source hashes without replacing samples based on prediction. No image-array pool
is retained by capture: each saved frame is checked individually. OCR/Analyzer
are never invoked. The original video and audio remain unchanged; retained JPEG
stills are private sampled observations, not a lossless native temporal sequence.

The frozen plan contains179 requests. Actual capture produced179 frames with174
distinct encoded source-image hashes, 5 exact duplicates, and0 overlaps with the
reserved prior-source hashes. Source/decoder/code/plan hashes passed terminal
checks. Capture time was13.406seconds; OCR calls, Analyzer calls and generated
events were all0. Peak RSS was not measured. An earlier pre-capture plan was
superseded after validation changes and was not decoded or overwritten.

Latest plan SHA:
`8a7a175fe2f9ac5f68405ae9c27cae3d58ce318318ce32524cd8251e4f1ab007`.
Capture receipt SHA:
`e3e0092ae0efcb8de15f87ce4ec8a9abcc7f821f217a439f8349cb94c805706a`.

The already fixed three-component discovery kernel splits the174 unique parents
into87training/87held images. Per configured ROI there are18 row proposals,
5 training-support rejections,13 supported proposals and10 support clusters;
the existing training-frequency cap returns4 candidates. Their training support
is13/12/11/11 and held acceptance11/13/13/7. These are unreviewed shape matches,
not correctness, recall or qualification. Developer visual inspection finds
purchase-like text in all four retained variants; no reviewed result reference
is established. Investigate training-only cluster diversity/pruning separately
from source coverage rather than interpreting a capped candidate list as proof
that a result was absent. Do not use held outcomes to select a new candidate.

Fresh discovery receipt SHA:
`e68c80f42fe053f63e83327b82bc462fb05df823057f2554ea8127a20c8ed2ee`.
The earlier three-reference transcription request remains pending and unchanged.
No semantic label, production setting, reference sidecar or qualification is
installed. New positive matches do not justify releasing Round events.

Related source-capture/discovery/semantic/geometry/native/lifecycle tests:
161passed. Ruff, mypy (132 production files) and diff checks pass. The freshly
fetched main remains`c11ec6d`; other branch work is not overwritten or used as
match_002 proof. Round start/end, Package affiliation and Full E2E completion
remain unproved; these source/reference steps do not redefine that objective.

## Reviewed purchase reference and actual native input (2026-10-14)

The human explicitly transcribed the three originally requested reference
candidates as purchase-phase text. Freeze exactly those three reference labels,
original parent/asset/report/page hashes and trusted conversation provenance.
Do not label the thirty held images, other ROI candidates, Round boundaries,
identity, continuity or adoption from this response. Original generation bytes
and all reviewed source assets were verified before recording the response.
The response and complete label record remain private and Git-ignored.

Private transcription receipt SHA:
`92d76cccbc3c484ddb47652166d74a23de7a13633014dc537115a6a3036054ee`.

Use the first frozen candidate by the existing training-only order; do not
select a variant by held predictions. Bundle its unchanged reference/mask/groups
and exactly the three human-reviewed source parents using the existing frozen
phase-profile builder. The native semantic matcher admits3/3 training parents
at the unchanged0.90 threshold and spatial/contrast/support gates. The private
profile configures only `buy_phase_template`; neither similarly cropped end-ROI
candidates nor failed purchase matches become result/absence references. Existing
geometry, independent identity and numeric readers are preserved. No qualification
file or application setting is installed. This is a diagnostic candidate, not
independent held/negative/temporal qualification or production adoption.

Private frozen training manifest SHA:
`0ffed3f5722039308daa67de9196070dd9a691125e573863e920728d4cbcd419`.
Bundled-profile diagnostic SHA:
`24ad3a42794508cbe17be9698995209f04f1cf55211f72949c4a3d786240a1b5`.

Fresh production native-window decoding/Analyzer on exactly the earlier
first-start85 physical source rasters and integer PTS yields12 purchase-phase
observations, previously0. Geometry remains4fresh/56effective, Timer42accepted;
all primary states remain unknown. Source/decoder/profile/code terminal checks
pass; elapsed45.329seconds. No external readers, saved predictions, supplied
geometry, GT or expected boundary enters recognition. Qualification is absent
and released events remain0; the acquisition gain is not a measured start
recall/Full E2E improvement. No player identity or owned fact is inferred.

Native input receipt SHA:
`682b6f5a89f8e93dba4318592cb153d8a341e5d1c998f63c96ee0477630229a0`.

Next independently qualify held/negative semantic evidence and the positive UI
transition/source contract. A missing purchase match is still not proof of UI
absence, and source/result/end qualification remains unfinished. Existing frozen-
profile/semantic/native/lifecycle regressions:117passed. Ruff, mypy(132production
files), and diff checks pass. No production-code or canonical-Pack change was
needed for this reference/input checkpoint; no merge/adoption is performed.

## Fixed reviewed reference on separate source images (2026-10-14)

Measure the unchanged, human-transcribed old purchase reference on all87 fixed
held parents of the additional development pool. Source inventory/hash, original
discovery receipt, preview hashes and configured profile/assets were verified
before/after measurement. Use the native grouped semantic matcher and configured
ROI/subregion directly, without reference fitting, OCR, GT, expected state or
qualifier creation. This is an isolated reference-image measurement; it does
not establish runtime geometry, ownership or temporal continuity.

The fixed reference matches13/87 at the unchanged0.90 threshold. All labels
remain null. Nonmatches remain unverified, not automatically absent or negative
controls; matches are not automatically correct. The images are exposed same-
match development data, some near earlier samples, not a new independent temporal
holdout. No cohort accuracy, recall, false-positive rate or qualification PASS
is claimed from these predictions.

Prepare six targeted human-review cases: the first three matches and nonmatches
within each model group, at least15seconds apart inside the group, displayed in
source-hash order. Selection is explicitly prediction-stratified, not a random
sample or new blind cohort. The page shows broad source ROI crops and original
image links, no model scores, selected class or expected transcription. Human
review must supply the actual displayed text, absent or unknown; omitted cases
cannot acquire labels. Requested scope excludes event timing, identity,
continuity, adoption and the full87-image cohort. Such targeted image review
cannot substitute for episode-level/whole-pipeline qualification.

Private frozen measurement SHA:
`dd5f7655922fc7627412775dd8f2287022b7b90401e4823861e88963061b9517`.
Private review-page SHA:
`4c78913194b6cd9038bb3b836ae2dd17bf14bd8d5766b138f4a16425446f9eb2`.
The review receipt records source/preview/profile bindings and the recognizer
fingerprint at export. The implementation fingerprint is a post-measurement
export record, not an asserted pre-frozen code/temporal qualification. Raw
measurements and the complete review remain local; no original reference,
Schema, GT, Pack, production setting or recognizer is changed.

## Complete supported-training audit and six-case source review (2026-10-14)

Add `--training-candidate-audit` to inspect up to16 supported training clusters
without scoring or rendering held images. The ordinary candidate cap remains4.
NCC, masks, contrast/groups, three-parent support and production recognition are
unchanged. Held scores/counts are explicitly null in this audit, semantic labels
remain null, and no qualification/profile is written. A regression replaces the
held scorer with a failure to verify that audit mode never calls it.

On the existing87training parents, all10 supported clusters per configured ROI
are now exposed, including the6 formerly omitted by the cap. Developer visual
inspection finds purchase-like text in every retained reference, not a round
result. Therefore the cap alone does not explain missing result references.
No semantic approval is inferred for these additional references. Descriptive
training-only white-component analysis finds178 qualifying-height components
of20..90pixels and5 above90pixels; it does not establish that those5 components
are result glyphs or justify changing native recognition/acceptance thresholds.
Keep source/feature/three-parent-support insufficiency distinct from pruning.

The human subsequently reviewed exactly the6 previously requested source cases:
three include purchase-phase text, two transcribe different visible menu text,
and one explicitly reports no text. Preserve the complete literal response,
source/preview/report/page hashes and trusted reply reference locally. Do not
turn an ancillary Round caption into Round-ID GT, reinterpret other text as a
runtime phase-disappearance proof, or annotate the other81cohort images.

The previously frozen matcher agrees with all6 target-reference classifications:
3 reviewed target matches,3 reviewed target rejections,0 reviewed classification
errors. These are prediction-stratified targeted image cases, not an accuracy
estimate for all87images, a randomized independent temporal cohort or full
qualification. One rejection has explicit absent text; two have alternative
transcribed text. No runtime absence checker, event or adoption is authorized.
No profile/threshold was tuned to this response.

The pending six-case transcription is resolved. Start/transition/source,
result/end, geometry coverage and whole-pipeline qualification remain separate
unfinished gates. Related discovery/semantic/frozen-profile/global-lifecycle
regressions:108passed. Ruff, mypy(132production files) and diff checks pass.

Final private training-audit receipt SHA:
`547562b5e25eed2ca7242e5cec36dc76509abf97b858ef15a089e2f4766d6c5e`.
The final implementation preserves all10 training candidates/assets/support sets
from the initial audit and still measures no held predictions. Earlier artifacts
are not overwritten. Private six-case transcription receipt SHA:
`fecdf81758893bb1ce6e9b57e09c05df6b51e1b780ed2809727f1f363d6af0ec`.

## Reuse retained development frames for proposal diagnostics (2026-10-14)

The failed exact-main baseline retained all13,287 sampled JPEGs. Reuse these
instead of decoding the recording again or introducing another capture sampler.
However, the persisted baseline trace is empty and the extraction service kept
per-image decoder PTS/hash identities in memory rather than writing sidecars.
The filename carries only a rounded timestamp. The run-level source SHA does not
prove an exact source-PTS binding for each retained image. These images are
therefore exploratory development inputs only, not qualification evidence.

Filter filenames before opening pixels: only rounded times in[0,719.999) enter
this inventory; no final evaluation holdout image is opened. The resulting4,320
native1920x1080 images span approximate filename times0.000..719.800seconds.
The unchanged diagnostic three-component row proposer finds803 images with rows
and841 total rows. Rounded(top,height) groups account for668 rows at(70,70),
83 at(50,80),22 at(70,80),21 at(60,70), and16 at(140,30). These are feature
counts, not purchase/result labels or detection accuracy. No candidate is selected
or accepted on these counts, and no temporal/held qualification is inferred.

SHA-256 of the ordered inventory (relative filename bytes followed by each
image's SHA-256 digest):
`cf80c2683a80489c88b70981b292cbd1939ee53553e4e1c682440b173a883431`.
No source image, original video or existing receipt was modified.

Training-only inspection of two large connected components from the previous
sparse pool reveals expanded-map outlines, not result glyphs. This is developer
feature diagnosis, not human semantic annotation. Raising the glyph-height cap
to admit those components would also admit map geometry and is not justified.
Keep the threshold/height/group/support conditions unchanged. Sparse sampling,
occlusion, feature extraction and semantic qualification remain distinct gates.
The resolved six-image human transcription stays unchanged; no additional image
is assigned a human label. Related discovery/capture/frozen-phase/semantic tests:
72passed. Scoped Ruff and git diff --check pass. No new whole-video E2E or
real-video improvement is claimed.

## Feature-selected source recapture, without GT (2026-10-14)

The retained-frame inventory identifies81 development images with rows in the
rounded(top,height)=(50,80) feature bin. Selecting the first such image at least
15seconds after the previous selected example, developer inspection finds actual
result-caption glyphs in two examples. This supplies a concrete next action:
recapture these source-selected images densely enough to test the unchanged
reference constructor, rather than widening glyph dimensions or lowering NCC.
No independent semantic annotation follows from developer inspection.

A preliminary exploratory fit to all81 retained crops (no held scoring or
qualification) yields84 proposals,12 insufficient-support rejections,
72 supported proposals and16 distinct support sets. All use the existing
three-group masked NCC>=.90 and minimum three distinct image hashes. Adjacent
frames can share one display episode: these counts cannot establish independent
episode support, temporal continuity, precision or end-event qualification.

Add `scripts/diagnostics/recapture_banner_features.py` with explicit freeze and
capture modes. Selection inspects development filenames before pixels, uses
only the configured ROI and explicit structural bins, and binds all inspected
image hashes plus layout/partition/code/toolchain. The frozen requests are
approximate filename times, never asserted decoder PTS. Capture obtains fresh
decoder ticks/timebase/video/image hashes, verifies the source and all inputs
before and after, rejects missing exact identities or incomplete coverage, and
writes private source records compatible with existing discovery. Output marks
feature-conditioned selection, no independent temporal cohort, no semantic
labels, no generated events and no qualification. This is not a production
sampler or recognizer change, and it cannot authorize adoption.

Private81-request plan SHA:
`fe6c190d5699051d26f5a6c3a54d575eb23ea4a9c40983d6c3f382064c5f2135`.
It binds4,326 inputs. Real-source capture has been started; completion and
post-run integrity checks must be inspected before using its result.

Nine new synthetic cases cover holdout pixel exclusion, invalid feature bins,
exact identity requirements and source mutation rejection. Related tests:
81passed; scoped Ruff, production mypy(132files), git diff --check pass.
No new full E2E, Round events or formal lifecycle improvement is claimed.

## Exact source-bound result-reference candidates (2026-10-14)

The initial recapture launched a redundant full ffprobe PTS scan. Confirm its
live process and the existing valid exact-PTS cache (132,855 decoder frames)
before deliberately cancelling that scan. This was a diagnosed redundant-work
cancellation, not an inference that an observation timeout meant failure. The
interrupted run exits130 and supplies no accepted capture result. Preserve its
plan; do not overwrite or treat it as successful.

Use the existing CachedVideoService, binding its implementation into a new
versioned plan. It validates the cached payload/source/timebase/ticks and primes
the same VideoService decoder; legacy float-only identities still fail the
recapture checks. Add before/after retained-image checks, plan-generation input
integrity checks and finite source metadata/resolution checks. These affect only
the diagnostic tool, not production recognition, the sampler or qualification.

New plan SHA:
`2e965cc9f59819ad5ca7f71dbe83f74e192433aaf31c15682c31d156c677868c`.
The new capture finishes successfully with81 distinct images and81 complete
decoder tick/timebase/video/image bindings. Source and frozen inputs pass both
pre- and post-capture checks. Probe-cache statistics:2hits,0misses,0writes.
Capture receipt SHA:
`09635ec58236c1bf3f3a5c970d49290f18367dbae2e2b240ebe9aa63a3809992`.
Selection receipt SHA:
`536926e47b418a2c0f4b8826fe7abf2e78ed8ae7cca5eb940b20b0e8773e2e38`.

Run existing training-only discovery on the recaptured pool:41training parents,
40held parents; no held scores or held galleries are measured/rendered. For each
configured ROI,42 training row proposals yield6 support rejections,36 supported
proposals and6 distinct support sets. Supports are22,21,20,20,16,12. Developer
inspection finds five WON-like references and one LOST-like reference, in contrast
to the previous sparse pool's exclusively purchase-like supported candidates.
This supports investigating input cadence rather than weakening matcher gates;
it does not prove static accuracy, episode independence or lifecycle recall.
The shared configured ROI names do not assign semantic meaning.

Discovery receipt SHA:
`1af726a0ed1a00973bf2b83ea389f63c16866b1e39153d548edb51ca7f0c6459`.
Review page SHA:
`fbca4e3db933890165b2153afbd6f6943527c0ad3ff728c2f633b6c7bdcf9938`.
Request independent human transcription of the six result-role references and
their source-parent links. Until answered, labels staynull. No production profile,
qualification file, event, GT or evaluation result is generated from this fit.
The feature-conditioned pool remains development diagnostic data, not an
independent temporal cohort or final holdout.

Related recapture/discovery/capture/semantic/frozen-profile/cache tests:
100passed; scoped Ruff, production mypy(132files), diff checks pass. Raw images,
PTS, paths and source receipts remain local. Whole-pipeline start/end, geometry,
positive transition, package affiliation and final E2E qualification remain open.

## Reviewed result semantics and frozen held measurement (2026-10-14)

Human reply explicitly transcribes both ROI sets:1,2,3,4,6 as WON and5 as LOST.
Preserve the literal response in a separate immutable review receipt, bound to
the unchanged discovery report/page/assets/source parents. The configured
center-phase ROI therefore contains result text in these images; it does not
prove purchase phase. No held-image labels, boundary times, ownership,
continuity or adoption follow from this reference-only review. Receipt SHA:
`64837c106bc92d041cffccd44e1323d6894a8cee1ba54127a5d219fb2ac23c16`.

Add a frozen-candidate measurement CLI. It verifies source/layout/assets before
and after, reconstructs the same grouped NCC references using training only,
measures every preselected candidate in original order and never reselects one
using held results. It rejects altered assets/source/layout, premeasured audits,
preassigned semantic labels and training/held overlap. Nonmatches remain unknown,
with absence_checked=false and runtime_transition_authorized=false.

On the40 development held images, candidate1..6 accept20,17,19,17,18,9 images,
respectively. These are unlabelled match counts, not correct detections, recall,
precision or qualified independent episodes. No combined OR matcher is created.
Measurement receipt SHA:
`75bc3718bf430c90a921fa854c10f79138abb633e0011202c43edcb615b11e5b`.

Extend the existing diagnostic profile builder with an explicit positive signal
choice, defaulting unchanged to buy_phase_template. round_end_template uses its
own configured ROI and the existing semantic matcher. Absence/ownership signals
are rejected. Build one WON reference from the first training-ranked candidate
and the first three human-reviewed WON source parents, not from held ranking.
These three parents share one display episode and do not qualify temporal use.
The generated profile preserves the existing purchase reference/base assets,
has three matched training parents at NCC.90 and creates no qualification file.

An initial manual ROI-origin transcription was wrong; the constructor rejected
it for insufficient support before publishing any profile. Preserve that failed
manifest. Derive the correct absolute crop from actual configured ROI bounds
plus unchanged candidate-relative bounds in a new manifest. No matcher, mask,
glyph coordinates within the ROI, threshold or reference image is altered.
Successful manifest SHA:
`ec09cd07dedcb2e10952d55b0f81f2f3f02f4d4ac6cb94a27edbeb30e172ef65`.
Diagnostic receipt SHA:
`da96ead7f740a01e0534047c540f85bac6bff64260c9e1ab8ca4f065ee8802fd`.

This is a local diagnostic profile only, not production adoption or a Round
end detection result. Independent source/geometry/UI-transition qualification
and actual downstream package/trace/full-E2E proof remain required. Raw assets,
source paths and exact PTS stay local; only aggregate and hashes are shared.
Final related tests:111passed. Scoped Ruff, production mypy(132files) and
git diff --check pass. No current full-suite or formal full-E2E success is claimed.

## Source-native result input comparison (2026-10-14)

Run the same85-frame continuous development window through RealHudAnalyzer with
the purchase-only diagnostic base and the reviewed WON diagnostic profile.
Both decoder contexts pass terminal source integrity checks and unchanged
profile/recognizer fingerprints. Physical video SHA, PTS ticks/timebase and pixel
hashes match for every paired frame. Source epochs intentionally differ because
input fingerprints include the selected profile; never join proof chains across
those profile-specific epochs.

Both runs have28 fresh geometry successes,68 effective successes,40 retained
frames and17 geometry-invalid frames. Both accept26 timer displays and38 paired
scores; all85 player states remainunknown. Their System observations are equal.
This is an input comparison, not evidence of owned-player validity or Round
event detection. The default diagnostic entrance did not persist unqualified
UI scans, so its empty qualified evidence/flags could not measure result text.
Preserve those first receipts rather than misinterpreting them as matcher failure.

Expose the existing Analyzer include_ui_measurements option through an explicit
CLI switch, defaultfalse. The existing binder saves producer scans in
system_measurements with scope=unqualified_current_frame and
qualification_required=true; they never enter system_evidence. Repeat the
paired window with this option: the base has0 result matches, the WON profile
has16 in one contiguous native run. Matched NCC min/median/max:
.943844/.974662/.978336. Phase absence remains0, qualified System evidence rows0,
qualification loaded/createdfalse and events released0 in both runs.

Only2 of the16 result-matched frames also have an accepted timer display, and
only2 also have a paired accepted score. Do not infer missing values or treat
this as a proven score-update/end transition. Input availability and temporal
qualification still need separate verification, including later confirmation
frames and distinct display episodes. The target window is development-only
retrospective input diagnosis, not training material or independent full E2E.

Base UI-measurement receipt SHA:
`a543ade032fb0ee1a6eed4a19799849961dffb179035ea6ee4c53977538b82eb`.
WON UI-measurement receipt SHA:
`7e661d11fead0b00e8edf0f88bc36d0dca5e43e86da3d5739c106403a5f60c83`.
Elapsed times:51.762seconds(base),52.997seconds(WON). Original measurements
without UI scans are preserved separately. No GT, Pack, threshold, production
profile, ownership gate or event policy changed.

Native-input/global-diagnostic/frozen-profile regressions:56passed. Two new CLI
cases verify defaultfalse, explicittrue and no qualification/event release.
Scoped Ruff, production mypy(132files), git diff --check pass. Real-frame scans
prove only measured input acquisition, not lifecycle or full-E2E completion.

## Follow-up input availability and explicit source assurance (2026-10-14)

Measure the subsequent85 native development frames with the same frozen WON
diagnostic profile, without changing readers, masks, thresholds or GT. Terminal
source/profile/recognizer integrity checks pass. Counts:6 fresh geometry successes,
56 effective successes,50 retained frames,29 geometry-invalid frames;36 accepted
timer displays,33 paired accepted scores and56 result-reference matches. Of the
matched frames,19 also have both an accepted timer display and paired score.
All85 player states remainunknown, qualified System evidence rows0 and events0.
Receipt SHA:
`64b1d2d34845194547fcc93e419be27c7b4221e170271d5e1a0891c768ace4e1`.
Elapsed42.732seconds. These availability counts are not reviewed value accuracy,
precision/recall, a proven score update or a Round end.

The earlier two joint observations were therefore insufficient to conclude that
the readers never acquire post-result inputs. Keep input availability separate
from transition/continuity qualification. The follow-up decoder starts a new
analysis context; do not stitch these independent receipts into a lifecycle
proof, carry geometry between them or imply one uninterrupted qualified epoch.
Next temporal verification must retain one source-owned continuous sequence and
its actual preceding/following evidence, not a concatenation of saved outcomes.

Register `datasets/input_contracts/match_002.unedited.json` from the human's
source-specific unedited-screen-recording assurance. It uses the existing strict
UneditedInputContract format and exact source SHA; it excludes intentional user
editing only. It explicitly does not certify capture pauses/freezes, frame loss,
observable game progression, scene continuity, boundaries, ownership or profile
qualification. No GT/expected state/PTS is present, no default runner/profile
selection changes and no qualification or event is released by registration.
Contract SHA:
`f3e0fd8e0cb8bb3da224f05c1cac8909e31400e56f1794a9473ef3f0d5539ead`.
The separate original provenance review remains unchanged.

Two new tests load the registered source contract and reject reuse for another
source. Related source-assurance/UI-start/UI-end/native-input/CLI cases:86passed.
Scoped Ruff, production mypy(132files), git diff --check pass. Existing
match_001 source contract/GT/Pack remain unchanged. No production profile is
adopted and formal lifecycle/full-E2E completion remains unproven.

## Continuous input gate diagnosis and latest-main integration

Replace isolated prefix/follow-up comparisons with one continuous169-frame
development decode. It has one source epoch and exact256-tick cadence, with
34 fresh geometry successes,152 effective successes and118 retained frames.
Accepted inputs:67 timer displays,90 paired scores,100 result matches and23
joint timer/paired-score/result observations. All169 player states remainunknown,
qualified evidence rows0 and generated events0. This is source-bound input
availability, not an end decision or independent temporal qualification.
Pre-integration receipt SHA:
`75538c101bd06d360871246f76adc098c4370f3c6c7837656c877b0d3d242bab`.

The two different accepted score pairs are separated by three unread frames;
there is no adjacent accepted old/new pair change in this window. All three gap
frames have valid geometry, an accepted timer and enemy score, but no accepted
ally score. Native reinspection localizes the ally numeric ROI in all three.
The existing OCR emits a value at confidence.82476738, which the unchanged
configured.90 floor rejects. This identifies a conservative numeric acceptance
gap, not a proven invisible score, geometry failure or source discontinuity.
Do not lower the floor, bridge the gap or infer a missing value to manufacture
the current end contract's adjacent-score evidence. Source pixels from this
targeted diagnosis are not training material. Partial failed inspection artifacts
are preserved separately from the completed three-frame inspection; images and
raw OCR remain local.

Fetch and inspect latest main `edc3b684aadac25b076665dcbb55bda254d335f3`.
Integrate it into the work branch without conflict (merge2081977), preserving
the upstream strict native replay, Trace confidence representation, aggregation
and Windows I/O changes. No direct main push or profile adoption is implied.
The recognizer fingerprint changes from the historical
`a1806645ccd1ce844fa1c971577abfbccef74375c082fbfd48fe733c1e68d467`
to `87f4bcea8b1699dbad965b634b06ebd4095dbb4519bd55ac4b8495b1d486e008`.
Historical receipts/qualifications must not be resigned or presented as current.

Repeat the same continuous input window with the integrated implementation.
The physical source identities and System observations match the historical
run exactly, including all availability counts and unknown states. Terminal
source/profile/recognizer checks pass, qualification remainsfalse and events0.
New receipt SHA:
`224756172471226092f802894a259d5b5c108d22e57f4dafe8112fd00628efb9`.
Elapsed87.033seconds versus92.927seconds historically; this is not a controlled
performance benchmark or new full-match E2E result.

The new I/O audit identifies70 previously implicit text operations in this
branch's diagnostic JSON/response handling and synthetic fixtures. Review those
protocols and declare UTF-8 explicitly, preserving binary operations, recognition
policy and all thresholds. Remove unrelated formatter-only changes after AST
equivalence checks and wrap only affected long calls. The final audit inventories
597Python files/1,805I/O sites with0unclassified sites. Old diagnostic-code hashes
remain historical; immutable plans are not rewritten to hide code changes.

Related post-integration tests cover source-native/UI contracts, frozen references,
numeric-review guards, encoding inventory and both confidence policies. Production
mypy checks133files. Ruff's CI scope (src/tests/scripts/e2e) and changed diagnostic
files pass; unrestricted root Ruff also visits original supplied packs and has
remaining errors there and in other unchanged diagnostics. Do not modify original
packs to force that broader check green. Latest-main formal full E2E and
independently qualified Round events/package affiliation remain unfinished.
Final checkpoint verification:273related tests pass, CI-scope/changed-file Ruff,
mypy(133production files), zero-unclassified I/O audit and git diff --check pass.

## Second development result episode: unchanged-policy input measurement

Measure a different development result episode using the same diagnostic-only
WON profile and integrated recognizer, without changing confidence floors,
reference selection, end-transition policy or production defaults. The continuous
native decode contains169frames in one source epoch at exact256-tick cadence.
Geometry succeeds freshly67times and effectively157times, including90retained
frames;12frames remain geometry-invalid. Accepted inputs include91timer displays,
71paired scores,13result matches and1joint timer/paired-score/result observation.
There are two distinct accepted score pairs but zero adjacent accepted score
changes. Eight score runs last at least four frames, with a longest run of eight.

Thus this second episode also does not supply the unchanged end contract's
adjacent-score transition. This is evidence about input availability, not proof
that all result episodes fail, that a particular missing glyph is unreadable or
that the end policy should be relaxed. Do not bridge missing reads, reuse these
targeted source pixels for training or count separate episodes as one continuous
proof. All169player states remainunknown; qualified evidence rows and generated
events remain0. No qualification is created or profile adopted, and full-match
E2E completion remains unproven. Detailed source images and observations stay
local; only aggregate counts and this receipt hash are shared:
`c8b2158609dbc09518de520ca965dbe420adad9aeaf5c563530d4cd15326ca7e`.

## Reproducible native score-gap classification

Add a bounded diagnostic reducer to the native input CLI. It validates one
source identity, exact cadence, positive time base and per-frame pixel hashes
before classifying accepted paired-score availability. The existing production
score confidence predicate is reused unchanged; a nonnull low-confidence value
is not accepted. A detected source break resets score history rather than
joining the surrounding observations. Adjacent changes and changes separated
by missing readings are counted separately, without releasing an event,
certifying source continuity or creating qualification. The shared aggregate
contains no score values, source timestamps, pixel payloads, paths or OCR text.
Original local receipts are inspected read-only, not rewritten or resigned.

Apply the reducer to both existing continuous development receipts. Each has
one nonadjacent observed score change across three unavailable frames and zero
adjacent changes. In the first episode all three gap frames lack the ally score;
in the second, two lack the ally score and one lacks the enemy score. None of
these particular change-gap frames is classified as geometry-unavailable.
This separates numeric acceptance failures from geometry availability without
claiming the missing glyph value or proving an end boundary. The next reader
experiment must use independent unlabelled development material and frozen
review/negative controls, not these targeted gap images or final holdout.

Regression coverage checks missing/low confidence, source-break reset, mixed or
gapped native provenance, returning to the same score, empty input and absence
of private payloads. Production recognition policy, profile adoption, safety
thresholds, original validation packs and qualification requirements are unchanged.
Final verification:104related tests pass, scoped Ruff passes, production mypy
passes for133files, and git diff --check passes. These checks do not establish
real-video boundary accuracy or full-match E2E completion.

## Single fixed score-padding experiment: rejected

Compare one bounded blank-border preprocessing proposal on the existing24-image
exposed development numeric review. No targeted end-gap image or final holdout
is used. The measurement reads only the original unlabelled blind ROI receipt,
not its separately frozen numeric labels. Verify all ROI hashes, the development
partition, OCR executable and preprocessing/reader source before and after
measurement. Keep original pixels and receipts unchanged. Both arms are retained;
there is no per-frame best-result selection, training, profile adoption or
qualification. The confidence floor remains.90 and the integer format unchanged.

The fixed proposal adds a dark blank border of half the localized crop height,
capped at64pixels, before the current grayscale PSM7 digits/colon OCR. Both arms
use the same unchanged localizer and OCR settings. Compare predictions afterward
against the existing independent numeric transcription, matching the review
receipt, source video and individual ROI hashes. Of22visible instances per side,
baseline/padded correct counts are13/7 for ally score and15/2 for enemy score.
Both arms have zero wrong accepted values and reject both absent-score cases per
side. Thus padding alone worsens acquisition and is rejected; do not repeatedly
tune border sizes on this exposed cohort. These24points are not fresh independent
qualification or a cross-match result. Baseline is a current diagnostic rerun,
not a replacement for the immutable historical numeric receipt.

An earlier trial also changed inverse bright-text thresholding and whitelist,
so it is confounded and cannot establish a padding-only effect. Preserve that
local record rather than overwriting it or hiding the settings difference. It
does not authorize selecting either arm or adopting a new production reader.
Current native settings were inspected explicitly before the corrected single-
variable comparison. Any future thresholding proposal needs a separately frozen
experiment and independent prospective review/negative controls.

Corrected measurement receipt:
`f7c1fdbd0088080c2ee57741b1fd3ffd9dfd5d412610e7f92abe266d311f20b8`.
Confounded historical measurement receipt:
`c58dd447192948c97e853eb98d8394aac4a26c51c56762294f590184798642f9`.
Existing frozen numeric-label receipt:
`c03adcb752e8ca9764c686df065fa45a5f2c73af8e279eae8fd72a847872074a`.
Raw strings, images, local paths and numeric labels stay private. No source
timestamps, GT labels or expectation data enter the production recognizer.

Synthetic regression checks the exact fixed border, unchanged input pixels,
confidence/format rejection, missing localization, holdout exclusion, labelled
input rejection, duplicate/hash/source mismatch, bounded summary and preservation
of raw local diagnostics. No runtime reader, safety threshold or lifecycle
qualification policy is changed.
Final verification:116related tests pass, scoped Ruff and production mypy
(133files) pass, and git diff --check passes. Full E2E remains unfinished.

## Fixed held result-text review prepared, labels pending

Resume semantic input qualification rather than repeatedly tuning score OCR on
the same exposed windows. Prepare a prediction-free broad-ROI review from the
original40-image development held inventory. Select six indices uniformly in
the original frozen order:0,7,15,23,31,39. Neither measurements, candidate ranks,
GT boundaries nor expected states select these images. The original discovery
receipt remains training-only; its separate measured outputs are not read by
the review preparer. Historical training-code hashes are not rewritten or
resigned, and no old qualification is inherited by the new review utility.

Verify the original layout/selection hashes, disjoint training/held images,
complete held source inventory, exact source-bound PTS and frozen development
partition before rendering. Recheck source/receipt/code bytes afterward. Source
photos and broad configured result ROI crops remain private; the page exposes
no candidate crop, score, OCR prediction or expected transcription. The new
receipt contains six null labels, not inferred semantic truth. Human review is
requested only for visible text, not event time, source continuity, ownership
or adoption. Nearby frames in this feature-conditioned pool are not independent
temporal episodes, and these cases cannot alone qualify UI end transitions.

Blind receipt SHA:
`a326bb1d721788edcf736744093f68db3d77890cef03b8daa46a7f2db56ebc9c`.
Blind page SHA:
`3c0eecb3dec16c5ba37077d6f1ec2bc7c7e793bd3f15ca55212b7ac0c855c28f`.
No response or semantic labels have been received at this checkpoint. Leave
them pending instead of interpreting a matcher nonmatch as an absent display.
No profile, runtime reader or qualification policy is changed.

Regression checks fixed selection, bounds, source/asset mismatch, training/held
overlap, holdout rejection, prediction-bearing input rejection, unlabelled
output and unchanged sources. Related tests127pass; scoped Ruff, production
mypy(133files) and git diff --check pass. Formal full E2E remains unfinished.

## Incomplete-round downstream integration safety

While the independent held-text response remains pending, extend synthetic
integration coverage through the real RoundPackageBuilder, FactBuilder,
Round Package Schema validator and Trace adapter. Supply explicitly synthetic
accepted boundary fixtures: an initial start without an end, then an independent
next start and its end. These are not recognizer outputs or video qualification
cases; no source pixels are decoded or qualification generated by this test.

Check UNKNOWN, spectator and remote observations at both zero and accepted
aggregate HUD quality. The initial package remains incomplete, no first end is
invented, and the second start belongs only to the second package. Accepted
current-point timer facts survive zero aggregate HUD quality with their original
reader confidence and HUD provenance; snapshots obey the existing aggregate
quality gate. Where snapshots are accepted, explicit changing timer displays
exercise assignment at the next start timestamp rather than the unchanged-state
two-second thinning branch. Events, retained snapshots and facts stay within
their correct package. Fact enrichment does not duplicate timer facts or local
fact IDs. System event confidence and evidence attributes pass through unchanged.

Player HP/weapon/ammo stay null or absent, and unowned HP/ammo/weapon values are
rejected by the existing HUD model before downstream processing. The initial
fixture attempted those forbidden values and was corrected to valid unowned
observations, with separate rejection coverage; the production contract was not
weakened. The Trace retains per-field timer confidence without attributing self
ownership. Inputs remain unchanged. No production implementation, safety floor,
Schema, original GT or validation assertion changes are needed for these cases.

Nine new synthetic cases pass; the related package/fact/trace safety suite passes
113tests. Scoped Ruff, production mypy(133files) and git diff --check pass. This
verifies downstream handling of supplied safe boundaries, not that current
video readers detect those boundaries. Independent temporal qualification,
source-negative coverage, real Round events and formal Full E2E remain pending.

## Further untouched numeric cohort feasibility

Before collecting another numeric cohort, inspect only non-GT source sampling
metadata from eight existing geometry/numeric/banner diagnostic receipts. There
are521point entries at480distinct PTS. Retaining the existing two-second exclusion
radius, their neighbourhoods cover the entire720-second development interval.
A metadata-only search of60fixed half-second-offset phases for a30-second
period yields zero eligible points at every phase, below the existing minimum
of eight. This is sampling feasibility, not pixel or numeric accuracy evidence.
No source image, OCR output, expected value or final holdout pixel is opened for
this check. Inventory receipt hash (canonical sorted path-to-SHA mapping):
`bcf93ecbafe1747cb55219d26e84ea83f38cd167965eb5a46f6384af79782015`.

Do not weaken exclusion/minimum-support settings, discard banner sampling
history or rename already exposed material as a new independent cohort. This
does not prove all source frames are duplicates or that no further diagnostic
experiment is possible. It means the present untouched-cohort protocol cannot
produce another independent batch within development. Additional footage or an
explicitly different, honestly scoped experiment would be needed for that route.
The six-image held result-text review is still available and pending; finish
that independent annotation before claiming new semantic input qualification.

An initial inspection incorrectly suspected the prospective probe lost its
template profile after copying the layout. Following the actual variable shows
the Analyzer still uses the original trial layout/profile; the supposed bug is
not present. Discard that attempted change and preserve both production and
diagnostic code unchanged. No historical receipt is altered, no full baseline is
rerun and no new profile is adopted in this feasibility checkpoint.

## Six held result-text transcriptions received and compared

The trusted human reply supplies explicit visible text for all six frozen review
images, resolving the pending transcription only. Preserve its literal response
privately, bound to the unchanged review/page, source video, historical matcher
measurement and previously reviewed reference receipt. Verify source images and
ROI hashes before freezing the response; never promote this text confirmation
to boundary timing, continuity, player ownership or adoption approval.
Human transcription receipt SHA:
`9669d9ec6109704ace3987ec5777440a1f4e229f82d009d3846b1d64910106e9`.

Compare all six original candidates in their frozen order, without rerunning
OCR/Analyzer, changing the.90 floor, selecting a new candidate or editing old
outputs. The first previously selected reference matches all three reviewed
examples of its text family and does not accept the three opposite-family
examples. Candidates3,4,5,6 have the same3positive/3opposite-family outcome;
candidate2has2positive matches and1miss, with0opposite-family accepts. Keep that
miss visible. Unknown matcher presence remains null on nonmatch, never a proved
absence. The comparator separately scores unknown human labels as unscored and
rejects altered floors, invalid scores and inconsistent presence measurements.
Comparison receipt SHA:
`291b564fe1eec9f892b405ebc8cf932e8f743adafeaff4d6182cee50f5ad7ed4`.

These six images all contain result text. Opposite-family negatives assess
text-family confusion, not false acceptance on normal gameplay, purchase menus,
maps or absent result displays. Nearby source frames also do not establish
independent temporal episodes. Therefore this result does not complete result
input qualification, UI end qualification or real Round lifecycle E2E. No
combined reference ensemble or new runtime profile is created from the held
comparison. Remaining work includes real non-result controls and independently
qualified temporal/source evidence, as well as numeric/geometry acquisition gaps.

Regression checks positive misses, opposite-family accepts, unknown labels,
null nonmatch, unchanged floor, image/page/measurement/reference binding drift,
read-only inputs and bounded aggregate output. Related tests92pass, scoped Ruff,
production mypy(133files) and git diff --check pass. Transcriptions and images
stay local; Git receives only the comparator, tests, hashes and aggregate summary.

## Frozen WON reference on existing reviewed other-text source controls

Use the six already transcribed phase/menu source images as a separate static
control measurement for the current frozen WON signal. No new annotations are
inferred from model predictions. Verify the original review/page/measurement
hashes and literal transcription bindings. All six source images are distinct
and none is a training image of the result reference. The source JPEG and broad
review PNG hashes match; the preview pixels equal the current broad phase ROI.
The result ROI is not identical to that broad ROI, but is fully enclosed by it.
This explicit containment prevents reusing a review of an unrelated image area.

Call the existing HudTemplateProfile.detect_signals on each full-size source
image, retaining semantic diagnostics for the configured round_end_template.
Do not invoke the Analyzer, create events, override geometry or assert runtime
absence. At the unchanged.90 threshold, all six WON measurements score0 with
null presence, and none is accepted. The original frozen profile fingerprint
remains `b751fb55c8f7995107c5554787f41daf63f9634dc60dd9935db3ea03e324efe5`;
recognizer remains
`87f4bcea8b1699dbad965b634b06ebd4095dbb4519bd55ac4b8495b1d486e008`.
Profile/assets, recognizer and source/preview bytes match before and after.
Private detailed receipt SHA:
`2eb340e679ce882496904b591a9ab62c1da440769d01111a881cdd794a4827f7`.

This is zero false acceptance on these six source-derived, previously selected
other-text controls only. They were selected earlier using a different phase
reference's match/nonmatch strata, not random gameplay sampling. Their review
supports visible-text classification, not source continuity, runtime phase/result
absence or event timing. The full source video is not decoded or reanalysed for
this image-only check. Normal gameplay, map, remote and varied visual-condition
coverage and independent temporal end qualification remain unproven. No runtime
policy, template, threshold, qualification report or production setting changes.
Related semantic/reference/review regressions79pass; scoped Ruff, production
mypy(133files) and git diff --check pass. Full E2E remains unfinished.

## Current native first-start inputs and producer-owned provisional boundary

Revisit the first development start with the integrated recognizer and combined
unadopted phase/result profile. The historical85-frame receipt had no raw UI
measurement envelope and predates main integration; do not infer temporal
availability from its isolated positive counts. The new continuous native pass
has85frames, one source epoch and exact256-tick cadence. Geometry is fresh4,
effective56, retained52 and invalid29. There are42accepted timer displays,
13raw phase matches,12joint phase/timer observations and11timer observations
with a confirmed phase flag. UI scan validity continues through the immediate
phase disappearance; the first following frame lacks a timer but later frames
have accepted timers. Input availability is not universally missing here.
Unqualified input receipt SHA:
`c851bef6ef59cea7052ea9f3169debf669fd1a91c7c3e8d3372885d12b5af037`.

Extend the diagnostic CLI with an explicit --practical-input-contract option,
mutually exclusive with the raw measurement option. It invokes the existing
collect_practical_lifecycle producer directly on decoder-owned native frames,
using the registered source assurance contract. Do not manufacture assured
evidence from saved measurement dictionaries or bypass reader qualification.
The existing production practical tracker supplies provisional boundaries; the
diagnostic rejects a confirmed overlay and never releases formal events.

The real source pass produces one provisional start candidate, with later
confirmation, at the independently approved start timestamp. All85physical
source identities and System observations match the preceding measurement pass
exactly. Tracker states include preparation, transient UI transition and active
candidate; detected source-break flags are0, not proof of source continuity.
Qualification is not loaded or created, and formal events remain0. The profile
and recognizer fingerprints remain unchanged and the decoder performs terminal
source integrity checks. Private producer receipt SHA:
`086b3b38e9e9b1ec608604d62b2f39d7f840a2abea922d5271d21aec088e1794`.

Pass those actual provisional boundaries/observations through the existing
practical RoundPackageBuilder, FactBuilder, Schema validation and Trace adapter
without invented HUD events. Both diagnostic fragments remain incomplete; the
accepted current-point timer facts number42, snapshots0, player HP facts0 and
formal boundary events0 in both packages and Trace. One start status is
provisional and all end statuses remain unknown. The builder includes
preparation context and an unobserved tail up to video duration; these prefix-
only diagnostic windows are not measured gameplay endpoints or a full-match
Round count. No private GT is used to partition them. This exercises the real
candidate transport, not strict boundary qualification or formal E2E success.

The CLI now refuses to overwrite any existing receipt. Default raw measurement
behavior remains unchanged. The score-gap reducer also resets conservatively
on producer-owned practical source-break fields when no measurement envelope
is present. No reader floor, temporal predicate, qualification policy or
production default is changed. Receipts generated before the final CLI metadata
and overwrite-guard additions remain historical and are not resigned.
Related native/practical/start/end/package regression tests143pass; scoped Ruff,
production mypy(133files) and git diff --check pass. Strictly qualified start/end,
full-match membership and latest-main formal Full E2E remain unfinished.

## Second-start transfer and authorized diagnostic gradient NCC

The unchanged combined profile produces0provisional boundaries in the next
development start's85-frame native window. Geometry is fresh7/effective31/
retained24/invalid54; timers30, phase presence0, trackerunobserved85. Source-break
flags0do not prove continuity. Receipt SHA:
`d098ced5202a5f21a99a668107b6bcd4ca6867379e00576886889867caa7c246`.

Classify failure only after inference using the independently reviewed start,
rounded to its native PTS tick. All37frames strictly before that tick lack valid
UI/geometry admission. Direct comparison with the rounded decimal had included
the boundary frame and counted38; correct the diagnostic classification, not GT.
A separate direct phase-template test on the same37source-pixel hashes accepts
36/37 at the unchanged.90floor (maximum.98635023). Terminal source integrity and
unchanged profile/recognizer are checked. It does not feed results back into
runtime calibration, observations or events. Receipt SHA:
`f9b110842d7a2f7314a27a255050e7cebb8078aa139971f57ab7634909da36c2`.

Extend the continuous window two seconds earlier without stitching contexts.
The205-frame run still has only7fresh/31effective geometries,0phase matches,
0candidates and0formal events. All157pre-boundary frames lack valid UI admission.
Overlapping85physical rasters, accepted values and producer evidence match the
short run exactly. This excludes a two-second warmup remedy, not all possible
full-match context effects. Receipt SHA:
`b1a21a757a98ba2c1e17cceb2bea27bb632b0465bbb206061173877263972b3a`.
Do not lower phase/OCR thresholds or train on these targeted source images.

The human authorizes a new geometry-only matcher comparison for diagnostics,
not production registration/adoption. Preserve the reply privately. Existing
matcher, NCC.90, three-anchor admission, identity separation and final holdout
remain unchanged; new scores are not equivalent to existing confidence.

The isolated diagnostic computes signed3x3Sobel channels, normalized by local
gradient magnitude with a fixed16floor, then masked NCC. Erode original support
by one pixel so every derivative dependency remains inside the geometry mask;
excluded digits/icons cannot enter via convolution. Require64support pixels,
reject constant/insufficient support and nonfinite NCC locations. Existing
templates/masks/search areas and position/size validation are fixed. No runtime
factory, profile kind, identity evidence or qualification report is introduced.

Freeze algorithm and source hashes before comparison on existing28training and
24validation development images. Validation has two repeated image hashes;
retain the frozen inventory and report22unique validation images separately.
Training/validation images are disjoint. No GT/annotation or final holdout chooses
parameters, samples or references. Data is exposed development, not new holdout.

Fresh geometry accepts, old/new:training8/20 of28; validation3/12 of24 (also3/12
of22unique images). Removing one anchor ROI at a time yields0/72accepts for both,
or0/66unique source/removed-anchor combinations. These are artificial source-
derived controls, not natural-negative qualification. Increased acceptance is
not independently proved accuracy and cannot authorize production adoption.

The first frozen attempt stops on missing calibration-call arguments before
publishing measurements; preserve it. The repaired run evaluates full-frame
diagnostic geometry, not letterbox/crop detection. Frozen experiment SHA:
`9dd29492b0f959112a6e2d84ebcddf0766082a451655f54310acc6085020408c`.
Completed measurement SHA:
`5b55dda0b9829935176a30941c9866cf1d980cafd9b7cc2e7a8e2507c3b0175c`.
Later hardening binds original template/mask receipt hashes and recognizer bytes
on future runs. Original assets are separately verified; historical plans are
not rewritten to pretend those extra guards ran earlier.

Tests cover signed contrast/orientation, excluded content, constant/noisy/wrong-
polarity controls, erosion, immutable outputs, duplicate counts, source/reference
drift and holdout/split exclusion. Related79tests, scoped Ruff, production mypy
(133files) and git diff --check pass. Natural negative coverage, temporal
qualification, strictly qualified starts/ends and formal Full E2E remain pending.

## Fixed gradient matcher: anchor failure decomposition

Add an aggregate reducer to the diagnostic only. It separates below-floor and
unscorable matches, reports min/median/max scores and failed-anchor combinations,
and distinguishes frame counts from unique source/control cases. Above-floor
scores with rejected layout geometry are counted separately, not called valid
calibration. Inconsistent duplicate measurements and invalid/nonfinite scores
raise errors. Aggregates omit source paths, images, timestamps and annotations.
No matcher parameter, production reader, admission policy or profile is changed.

Reduce the preserved historical measurement without rewriting it. In24validation
entries, timer accepts12, HP23 and abilities24; all anchors produce finite scores.
Failures are timer alone11 and timer+HP1. All12entries with three accepted scores
also satisfy layout position/scale validation. For22unique images, timer accepts12,
HP21, abilities22; timer alone fails9 and timer+HP1. Duplicate entries are not
independent negative cases. The new retrospective aggregate receipt SHA is
`9805ad02a1ce8285cf37f780c2fd03f5b69effc8c0b1827c678e766f003c3fa9`.
It is a score breakdown, not another recognition run or qualification result.

Existing independent numeric visibility reviews establish whether digits are
visible, not whether fixed geometry is absent. A reviewed recording-pause state
likewise does not establish that HUD geometry disappears. Do not relabel these
as natural geometry negatives to manufacture qualification. Natural-negative
coverage remains outstanding; no runtime adoption is authorized by these counts.

Apply the identical fixed diagnostic matcher to the previously exposed205-frame
native second-start context. Freeze inputs before decoding, verify all205PTS and
pixel hashes against the preserved practical diagnostic, and check source video
integrity on decoder entry/exit. No GT or final holdout enters matching. All205
rasters are distinct. Fresh geometry accepts old7/new83; no all-score-accepted
case fails the position/scale guard. Anchor accepts are timer177, HP107,
abilities205. Failed combinations are HP94, timer24, HP+timer4. In this different
context HP is the main bottleneck; the validation-set timer bottleneck alone
cannot characterize transfer. No threshold or mask is adjusted after observing
these results. Wall time38.925seconds, including source-integrity/decoder work.

For post-inference diagnosis only, use the already reviewed boundary's native
tick to divide the unchanged result: pre-boundary157frames old0/new54 fresh,
post-boundary48frames old7/new29. This evaluation-side split does not train,
select or modify any matcher input and does not assert event timing accuracy.
There is no geometry retention, OCR, identity, lifecycle or event admission in
this isolated comparison. It creates0events and no qualification/adoption.
The initial preflight passed the window end to a partition verifier that
requires the frozen development limit; it rejected before creating an artifact.
Correct the invocation, separately bound the window to development, and retain
the unchanged partition policy. Successful frozen-plan SHA:
`652e90f955c841be2e05aa02ad813a9669cf501497454efdeda8362c8f46e196`.
Measurement SHA:
`0feb8bda314e29154f87c6693738c4b66d350c77ea573c250fce9d7262d08abb`.

Related geometry/native-prefix tests52pass, scoped Ruff, production mypy
(133files) and git diff --check pass. These checks and diagnostic acceptance
counts do not complete qualified real-video Round lifecycle or formal Full E2E.

## Separate blind source-geometry controls review

Extend the private geometry-review preparer to consume a complete external
development image inventory, independently of the frozen reference candidate.
Require the same source SHA, a valid frozen development/holdout partition,
bounded inventory, image hash/dimension verification and no image-hash overlap
with the candidate's training/validation sets. Bind both inventories and the
partition; check them again before releasing the review receipt. Existing
candidate-only review remains available and no historical receipt is rewritten.

Use all13images from the existing numeric contrast-selected development cohort,
not a subset selected by the gradient matcher's output. All13are distinct and
none overlap candidate images by hash. This is previously exposed development,
not an untouched holdout or independent episodes. Prior numeric labels do not
become geometry labels. No matcher, OCR, prediction, fitting, video decoding,
qualification or production adoption is run during review preparation.

The review shows unchanged reference/mask assets, configured guides and neutral
numbered copies of each original image. Copies preserve source bytes and avoid
revealing the earlier cohort's semantic directory name. Instructions explicitly
distinguish fixed geometry from variable digits/icons and allow visible, absent,
misaligned, unknown and unreviewed responses. No expected state or match score
is displayed. Ask the human to review geometry only; identity, event timing,
continuity and adoption remain outside scope. Labels are still unreviewed.

Private review receipt SHA:
`8fb52c4385e68330fb1962b0f8f9838d4a1fe27a85f396f6589d50d828f53f9d`.
Private page SHA:
`fce9bd6dc9a019370bdc052671ed64a3d762f8004d8a49824704d65785dc182a`.
Do not infer negative qualification from preparing a review or sending a request.
Tests cover non-disclosure, unchanged source copies, hash/partition bindings,
source mismatch, overlap, changed pixels and holdout rejection. The scoped
geometry test run42passes before integrating the newly fetched main.

Fetch origin/main and inspect the new Qt shutdown lifecycle change before
merging it into the work branch. Integrated main is
`7e480c2` (merge checkpoint `ec90051`); this is main-to-work integration, not
work-to-main adoption. The fetched changes touch GUI ownership/teardown and
related tests/docs, not HUD/Visual recognition or the frozen profiles. The
global recognizer fingerprint remains
`87f4bcea8b1699dbad965b634b06ebd4095dbb4519bd55ac4b8495b1d486e008`.
After integration, geometry, startup, GUI smoke and Qt shutdown process tests
82pass in20.43seconds; scoped Ruff, mypy(134sourcefiles) and git diff --check
pass. No full-suite or full-match E2E result is implied. Independent geometry
control labels are requested but not yet received; no negatives are inferred.

## Full regression exposed an orientation-bin precision bug

Run the complete repository test suite with the CI coverage command on the
integrated main/work checkpoint, without changing assertions or thresholds.
On macOS/Python3.12.15, OpenCV4.14.0 and NumPy2.5.3, the result is4050passed,
4failed,5skipped in429.47seconds; coverage86.65% exceeds the unchanged75%floor.
Private JUnit artifact: `main_7e480c2_integrated_v1.xml`. The four failures all
involve the unchanged abstract spectator-icon positive fixture. The detector
and failing tests are identical to origin/main; they are not introduced by the
geometry diagnostic or Qt merge. Do not report the full suite as passing.

Reproduce the reason without changing the fixture: native icon measurements
meet mean/contrast/sharpness, density, cell count and localized-group predicates,
but the orientation histogram has only7populated bins. A negative-X Sobel vector
has angle pi. Float32 radian-to-degree conversion moves it to approximately
179.99998degrees, incorrectly assigning that entire cardinal direction to the
preceding half-open histogram bin. Native histogram fractions include .157567
in[135,180) and .049758 in[180,225); shifted fixtures show the same issue. This
is a numerical boundary error, not evidence that a detector threshold should
be lowered or that the fixture's expectation should be weakened.

Compute arctan2/degrees in float64 in the presence detector and its existing
absence-only crosscheck. Keep Sobel, Canny, histogram boundaries,5%population,
eight-bin requirement, presence/absence thresholds, obscuration guards, identity
policy and all old fixtures/assertions unchanged. Do not round, snap or smooth
angles. Native bin fractions become .087077 and .120249 at the affected bins;
all8directions are represented. New synthetic tests verify all8exact canonical
vectors, signed-zero negative-X consistency, and distinct directions immediately
on either side of180degrees, without mutating inputs. Spectator icon, absence
guard and generation tests53pass after the fix; scoped Ruff, mypy(134files)
and git diff --check pass. An initial targeted invocation named a nonexistent
test path and collected no tests; only the corrected invocation counts.

This production numerical correction changes the global recognizer fingerprint
to `7c3654fc4f34b46633c01d61017458c959e5b5cae13b4d5915937f16c2467381`.
Historical profiles, measurements and qualification receipts remain bound to
their original recognizer version; do not rewrite or resign them to inherit a
new qualification. The geometry gradient matcher remains diagnostic-only and
unchanged. This synthetic regression fix proves no real-video identity or
Round lifecycle improvement; source-control geometry labels are still pending.

Re-run the complete CI-style coverage command at code commit `351b75c`, with
no source/test edits during execution:4056passed,5skipped,0failed,0errors,
430.04seconds and86.66%coverage (unchanged75%minimum), exit0. Existing4failures
are resolved and the2new numerical regression tests pass; existing expectations
are intact. JUnit counts include skips:4061total. The5skips are the opt-in
real-video-anchor integration test (not configured for this invocation), one
host-native Windows path test and three PowerShell-dependent tests. They do not
mean that the separately received match_002 source video is missing, nor prove
Windows or actual-video anchor accuracy. Final scoped Ruff, mypy(134files),
dataset contract38cases and git diff --check also pass.

Preserve both private JUnit artifacts. Before-fix JUnit SHA:
`7154d1962882dc8bde73c4f9a49fcf20309835dbf2cc3d1c58e041171229d62d`.
After-fix JUnit SHA:
`7449f79dce56a9c1b670a69a19643e87bc06c313058f538b6c82c73a27ceb63e`.
These are repository/synthetic regression results on macOS, not a formal
real-video Full E2E run. Keep the larger lifecycle goal incomplete, keep the
gradient matcher unadopted, and await the outstanding independent source-
geometry review before treating those images as positive/negative controls.

## Mixed control comparison ready; independent review remains the blocker

Add an evaluation-only CLI, `scripts.diagnostics.compare_geometry_controls`,
for the prepared external source-control review. Inputs are candidate, complete
source pool, review directory, explicit human label receipt, partition and new
private output path. It requires three unchanged .90 geometry anchors, verifies
frozen assets and review/page/source/guide hashes, bounds all frames to the
development partition, and rejects candidate-image overlap, omitted labels,
missing human-reply binding, contradictory duplicate labels and source drift.
JSON cannot authenticate its own author; the separate trusted human reply is
still necessary. No label file is generated from model predictions or defaults.

Measure every source image with both fixed matchers, including unknown and
unreviewed images, before reducing results against labels. Labels do not enter
matcher arguments, training or sample selection. Only three visible fixed
anchors establish a positive. Explicit absence of any required anchor establishes
a negative under the fixed three-of-three contract. Unknown and unreviewed
remain unscored. Qualitative misalignment alone also remains unscored: it does
not prove an offset beyond the existing numerical layout tolerance. Do not
invent a new spatial assertion from that label. Report frame counts and unique
image counts separately; neither is an independent-episode count.

The output contains bounded aggregate counts, hashes and fixed algorithm/profile
identifiers, not paths, image data, timestamps or transcribed source labels. It
always declares no identity evidence, events, qualification or adoption. Synthetic
tests cover mixed outcomes, both false accepts and misses, immutable inputs,
matching unknown/unreviewed images, changing only labels without changing matcher
inputs, review drift, holdout, overlap and cross-source rejection. Related49tests
pass; scoped Ruff, mypy(134files), CLI help and git diff --check pass. Production
code/fingerprint is unchanged from the preceding numerical fix. The earlier full
suite4056pass result predates this evaluation-only tool; it is not a new full run.

Do not execute real-image comparison yet: the independent13-image geometry
review has no reply/label receipt. Its page and review hashes remain exactly
the previously recorded values. Fetch origin/main again: no newer changes than
the integrated `7e480c2`. No test/decoder process remains running. The same
independent-review blocker has persisted across three consecutive goal turns;
safe regression repairs and the needed comparison tooling are now complete.
Further qualifying/adopting this matcher requires that human evidence and,
separately, adoption authorization. Repeating unchanged inference, extending
OCR searches or assuming labels would not resolve the blocker. The overall
real-video Round lifecycle goal is incomplete and requires user input to resume
the next qualification step; do not silently claim completion or relax safety.
