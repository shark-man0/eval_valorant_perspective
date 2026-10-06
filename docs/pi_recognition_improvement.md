# Pi real-video recognition investigation (2026-10-06 JST)

<!-- CURRENT_STATUS_START -->
Current status: strict profile06 standard native E2E completed with valid output hashes, schema and no processing error. Assertion counts are **22 passed / 56 failed / 4 not evaluated**, versus baseline21/57/4. Native evaluator failure-reason count remains57: one failed snapshot assertion now reports two field failures. Improved assertion: `GT-R1-SNAP-705`; previously passing assertions did not regress. Negative assertion failures and discontinuity violations remain0. There are5347 observations: unknown4540, live589, spectator216, buy menu2. All18 identity assets remain relative and production-loaded; safety thresholds are unchanged. Fresh geometry remains1. One boundary-incomplete round package exists with no detected round-start/end events; Visual events and map resolution remain0. Full source tests996 passed/6 skipped, Ruff and mypy remain verified.

Profile06 all-live fresh identity replay and semantic image review are pending. The private comparator was corrected to validate failure-reason multiplicity against assertion detail arrays, without changing native evaluation or assertions. The private audit lookup now uses the production cache filename's3-decimal timestamp formatting (at most0.5ms quantization), with conflicting decoded-pixel hashes rejected.

Portable timer-reader candidate07 standard E2E is running as `20261006T010024Z-a493a3cc` (detached runner22836). It uses unchanged identity assets and verified common production source; host OCR runtime is isolated to this child process. Windows runtime remains unverified. Environment profile selection is unchanged. Goal remains active; native failure-reason reduction and semantic safety are not yet proven.
<!-- CURRENT_STATUS_END -->

## Baseline and input integrity

Baseline native run: `20261005T135105Z-80024d30`, 3869 observations,
21 passed / 57 failed / 4 not evaluated. Negative assertions: 20 passed / 0 failed.
HUD unknown 3867, identity insufficiency 3869, each missing structure 3869,
Spectator reference unavailable 3869. Fresh geometry 1, effective geometry 3869,
insufficient anchors 3868. No rounds, Visual events or resolved map locations.

Video SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.
Validation Pack SHA256: `7f0b7798857670f08074adbeea73d24176967ad5bf1f2f7300d2c2f792cf956f`.
The video, pack, expectations and recognition thresholds are unchanged.
No Git staging, commit, reset, branch change or remote mutation was performed.

## Hypothesis 1: unavailable references are a profile selection problem

Problem: all current-frame identity structures and Spectator evidence are unavailable.
Evidence: `.env.local` selects the static `reference-seed` profile. Its sidecar
contains four unmasked geometry anchors, empty readers, no signals, and no
Spectator detector. All four relative anchor paths are readable. The earlier
Pi runtime record explicitly documents generation with `hud.calibrate`, which
only exports geometry; the E2E runner loads the sidecar but does not generate
identity references. No other private identity profile was present locally.
Windows reports describe generated private profiles but their image assets were
not transferred here. This is not evidence of ARM numerical drift or failed
Linux resolution of an existing identity reference.

Change/experiment: run the existing `hud.calibrate_profile` on 64 unlabelled
native-resolution video frames. Training and holdout remain separate. Generated
HP/Ability/Weapon references load without diagnostics; support is 28/28,20/17,
15/14 respectively. All reference thresholds remain .90. These are generation
support counts, not an all-frame accuracy claim.

Reference hashes:

| Role | PNG SHA256 |
| --- | --- |
| HP | `b54b6d20128a15fab7da46dcc6273f3787f76b5138ecc01c4830f5b819bfcd2d` |
| Ability | `ffc67ca043fabce50bd3cf984413d912a6b25f3ef79fb764c76da546e10dfb5b` |
| Weapon | `9c9bc886844b2ba3c0e3b1dc55cd7a2d0f87262e00e4288ce6b89ec0a67fdeb1` |

The existing automatic generator chooses a fixed-icon Spectator detector when
that ROI exists. This exploratory E2E measures existing behavior; it does not
qualify that route against the requested compound portrait/text/boundary policy.
A separate unchanged compound-panel generator probe is required. No Spectator
threshold, context veto or checked/panel_present requirement was relaxed.

## Hypothesis 2: all-or-nothing generation discards supported geometry

Problem: new geometry falls back wholesale to the static screenshot anchors.
Evidence: 64 rank-uniform saved real-frame samples produce only one temporal
candidate, top_match_bar. A mask/reference frozen on the even training samples
passes NCC >=.90 on 32 training and 32 odd holdout samples (minimum .9848 in this
preliminary cached-frame probe). The old generator requires three newly generated
anchors, throwing away that candidate even with a complete existing profile.
Static templates include changing timer, roster, HP, ability and world pixels;
no baseline anchor has a mask. Baseline confidence medians are .7762/.4410/
.5094/.4118 (timer/top/HP/Ability), explaining their runtime rejections at .90.

Change: freeze each candidate template/mask on training only; independently
validate holdout with at least three observations per split and comparable
prevalence. Keep the existing pixel variance/persistence selection constants,
NCC .90 and any higher inherited threshold. When fewer than three new candidates
are supported, combine them with readable inherited anchors only if the resulting
profile still has at least three anchors. Runtime still checks three geometric
inliers, position and scale. A new profile without adequate inherited geometry
still fails. Rejection stage and independent support counts are exported through
an explicit image-free allowlist.

The second profile uses the exact 64 JPEGs extracted by the first generation
(no new decode or sample selection). The three identity PNG hashes remain identical;
only top_match_bar geometry gains a validated mask. New and inherited anchor
provenance remains excluded from identity inheritance.

Tests: focused temporal + calibration/export tests: 15 passed. Ruff src/tests/
scripts/e2e passes; mypy src passes (86 files). The plain pytest executable initially
failed collection because scripts was not importable; `python3 -m pytest` is used
for the full verification. Full suite and two native-video E2E runs are in progress;
no final recognition improvement or goal completion is claimed yet.

## Windows checks still required

Native-frame PTS/decode correspondence and OpenCV masked-NCC numeric parity;
relative sidecar asset paths and transfer of every inherited asset (currently
some references are absolute Pi paths); portable FFmpeg/ffprobe subprocess and
packaged/PyInstaller resource resolution. Windows has not been tested in this work.

## Compound Spectator probe

Using the unchanged compound generator on the exact 64 extracted images: 32
training proposals, 32 reserved holdout images. Of training observations, 19
have boundary evidence, 32 text evidence, and two a supported portrait/complete
compound proposal. Both proposals self-match at 1.0 but support only one training
observation each (three required); no holdout is opened for selection. Generation
correctly refuses both. The strongest independent comparison for the first
proposal has boundary .9294, text .9864, portrait .8962 (recall .8962, precision
.9095), while the reverse portrait match is .8676. No threshold is lowered and
no fixed-icon result is represented as a compound reference qualification.

## Live run tracking

Exploratory identity-profile native run: `20261005T153829Z-f1a6683f` (tool
session 22968). Geometry candidate native run: `20261005T154118Z-898b49ff`.
Its parent runner terminated with code 143, but the actual analyzer PID 10645
was verified running; it was not restarted. A private observer waits for that
same analyzer, then runs the original evaluator on its completed actual trace,
preserving the run's original metadata/settings and recording file hashes through
`save_context`. It cannot claim an evaluation if raw status is not complete.
Recovered shared output is kept separately under ignored outputs to avoid
confusing the other active run's main summary. This is output recovery, not a
recognition improvement or a PASS claim.

The candidate run was re-polled after its wrapper termination. Analyzer PID
10645 and its ffprobe child were then confirmed missing, with no raw or trace
artifact. The recovery observer therefore failed closed without evaluator or
shared output. This is an interrupted run with no recognition result. Retry
only after the surviving identity-profile run finishes; do not overlap another
native-video job. Session 22968 remains the authoritative running baseline
experiment. No failed/passed counts are fabricated for the interrupted run.

## Follow-up authorization and portability

The user confirmed that Windows references were not explicitly transferred and
asked for Pi regeneration using the current video, existing generation mechanisms,
independent current-frame structures, value-invariant features and unchanged safety
thresholds. No further search for an assumed external profile is required.

Generated profiles now copy readable inherited asset bytes into content-addressed
relative paths. Nested template banks are localized recursively. Geometry/identity
path and content-hash exclusion is evaluated before bundling. A relocation regression
checks Unicode paths, exact bytes and preserved thresholds after moving both source
and generated directories. Missing assets remain unavailable. This addresses profile
portability without changing recognition scores or claiming Windows validation.

An unmodified-generator Ability experiment freezes four pedestal contour areas,
excluding icon content, charge diamonds and key/value text. No production Ability
matcher or layout change has been made; training/holdout and arrangement gates
must qualify this experiment before any adoption.

The initial full-suite baseline and an obsolete focused suite were cancelled as
superseded after further source edits; they are not reported as passed. Final focused
verification continues; the full suite must be rerun on the final source with the
established external-pack/headless environment. Concurrent native E2Es and redundant
suites are avoided for subsequent work.

## Value-invariant and compound generation controls

`calibrate_profile` now accepts `--value-invariant-only --compound-spectator`.
The former disables intensity-only generation/inheritance rather than relaxing
any matcher. The latter selects the existing three-component Spectator detector
rather than the fixed icon. Missing role definitions and independent support are
reported with allowlisted reason/stage codes. Generated profile
`pi-structural-20261006-03` is loadable, with no absolute or missing assets and no
loader diagnostics. HP support is 28/28, Weapon 15/14; Ability remains disabled
because the canonical layout has no qualified value-invariant Ability definition;
compound Spectator remains disabled because original training support is one.
`identity_reference_ready=false` is explicit. This profile is not adopted in
`.env.local`; the original baseline configuration remains selected.

A second Ability experiment excluded interior pedestal fill and charge/text pixels
and froze the contour areas before opening a new 64-frame bank with exact pilot
frame times excluded. Training support 20, holdout 12 fails the unchanged .80
prevalence condition. This is worse than the first 24/18 support result. Both
experiments remain diagnostic-only; no Ability mask matcher is enabled and no
threshold or support rule is tuned to rescue them. Metrics are in
`pi_identity_generation_metrics.json`.

Nested digit-template lists are now included in the asset fingerprint as well as
bundling/localization. A regression changes an individual bank asset without
changing JSON and verifies that the profile fingerprint changes.

## Compound neighborhood experiment

Hypothesis: uniform sampling cannot supply three independent repeats of the
compound portrait mode. Freeze bounded temporal-neighborhood offsets around
TRAINING-ONLY qualified compound proposals; original odd holdout pixels never
select the neighborhoods. This probe adds six distinct pairs from the existing
native frame cache, excluding all original pilot timestamps. The unchanged
compound generator evaluates 38 training and 38 holdout observations. It finds
five complete training proposals, a selected reference with training support 4
and holdout support 4 (minimum 3 each), at unchanged .90 per-component recall/
precision and unchanged prevalence criterion. All three component assets are
saved privately. Full-frame inspection of the selected source confirms a visible
portrait with adjacent two-row text and the left panel separator, rather than an
arbitrary world texture. This is a score-selected same-recording diagnostic;
there is no independent-recording or runtime false-positive qualification yet.
Next: make this training-selected resampling reproducible through the production
profile generator, verify source PTS separation and all accepted real-frame
appearances, and run real E2E with the supported compound reference. Ability
qualification remains necessary before claiming complete live identity.

Final-source focused verification so far: 17 passed for strict-generation,
relocation, geometry and export checks; one fingerprint regression passed.
The broader earlier focused suite also passed 29 tests. Ruff src/tests/scripts/e2e
and mypy src (86 files) pass. Full pytest is running with the external pack,
UTF-8 and offscreen Qt; OpenCV threads=1 is a resource setting, not a threshold,
sampling change or Pi-specific recognition branch.

## Continuation checkpoint

Active native E2E tool session: 22968, parent PID 10466, analyzer PID 10486,
run `20261005T153829Z-f1a6683f`, profile `pi-auto-20261006-01`. Last verified
progress: 72%, HUD timeline/event finalization. This exploratory profile retains
existing intensity-only Ability and fixed-icon behavior and is not a qualification
of the new value-invariant/compound profile. Do not restart while these handles
are live; inspect raw/evaluation outputs when terminal.

Active final-source full pytest tool session: 58701, PID 11394, log
`outputs/recognition-investigation/final-pytest.log`. It uses UTF-8, offscreen Qt,
external pack and one OpenCV thread. Do not claim a final result until exit and
summary are available. Ruff and mypy source checks have passed.

Next concrete work: finish the baseline exploratory E2E and compare every required
recognition/safety count with the original 21/57/4 baseline; integrate bounded
training-only compound proposal resampling with unique native PTS and frozen
holdout selection, verify accepted appearances/hard controls, then produce a new
strict relocatable profile and run the prescribed E2E. Ability contour experiments
24/18 and 20/12 were rejected; reassess feature extraction and independently
qualify a new representation rather than lowering confidence or support criteria.
Keep `.env.local` on the original baseline until a candidate is supported. All
images remain under ignored outputs. The goal is active and not achieved.

## User clarification and reproducible compound sampling

The user confirmed that the Windows-verified private identity images/masks were
not explicitly transferred to Pi and no complete copy is known on GitHub. Do not
assume another profile directory exists. Continue real-video regeneration with
the same production code/profile format and all existing safety gates.

Problem: the uniform pilot has complete compound spectator proposals but only
one matching training observation per proposal. Evidence: the earlier frozen
neighborhood diagnostic produced training/holdout support 4/4 without changing
component thresholds. Change: the common profile generator now performs one
bounded neighborhood extraction only when compound generation lacks a supported
training cluster. It chooses up to eight complete even-index training proposals,
using fixed offset pairs (-1.5,-1), (-.5,+.5), (+1,+1.5) seconds, at most 48 extra
observations. Original and additional holdout assignments are frozen before
decoding. No retry follows a supported training cluster's holdout rejection.
Requested-time collisions omit the entire pair. Missing extraction results,
duplicate actual PTS, seek discrepancies above .25 seconds or incorrect decoded
resolution reject all added observations with an explicit reason. Every component,
relative-layout, minimum-support and .90 confidence gate remains unchanged.

Tests: two sampling-plan tests, one diagnostic privacy test and three injected
extraction-fault tests pass. The fault-test fixture initially supplied densely
spaced timestamps, correctly yielding no safe neighborhoods; it was corrected
to a longer synthetic duration to exercise extraction rejection. Ruff and mypy
(86 source files) pass. The existing full pytest run began before this sampling
change and is still in progress; a final full-suite result is not yet available.

Additional cached runtime diagnostic: 128 new uniform samples; checked=60,
panel_present=5, unchecked=68. All five positive source images were inspected;
each contains the actual spectator portrait, adjacent two-line text and separator.
This is not an independent-recording negative qualification, nor an E2E result.
The detector preserves checked=false for ambiguous evidence.

Rejected Ability hypothesis: decorative wires outside the four ability icons,
charge indicators, pedestal fills and key captions. Freeze two outer support
groups before loading a separate 96-frame bank, excluding both prior experiment
banks. The unchanged scaffold generator reports training=48/holdout=48,
candidate_count=5, structural_rejected=8, support_rejected=40 and no supported
training candidate; holdout is not used to select another candidate. Do not
publish or enable this reference. The remaining Ability evidence is unresolved.

Native strict CLI generation for `pi-structural-20261006-04` ended with exit 143
and no diagnostic exception/output. The cause is unknown; there is no recognition
result to count. A retry uses a retained terminal session (33844), PID 12497,
log `outputs/recognition-investigation/native-structural-04-retry.log`.
The exploratory E2E remains session 22968/PID 10486 at 72%; full pytest remains
session 58701/PID 11394 (last observed 43%). Neither is a terminal result.
The baseline remains 21 passed / 57 failed / 4 not evaluated, with zero negative
assertion failures. Complete strict identity reference readiness is still false.

## Ability failure localization and asset readiness

The earlier four-pedestal candidate's scores were decomposed per independent
group without changing runtime scoring: groups 1..4 have training/holdout support
28/28, 28/27, 27/26, 25/20 respectively at .90. The full conjunction remains
24/18 and fails the existing .80 prevalence requirement. The fourth group is the
least stable. Inspection of even-index training crops shows that the old support
areas include changing fill/charge content; do not adopt the old candidate.

New hypothesis: retain only the lower fixed pedestal frame and exclude the full
fill area, charge diamonds and key captions before feature extraction. Frozen
support/exclusion coordinates were checked on training images only, then evaluated
on a new 96-frame bank excluding prior pilot/contour/wire timestamps. The unchanged
scaffold generator selects a candidate with training support 3, holdout support 0
(48 observations in each split), and reports holdout_rejected. This candidate is
rejected, with no image assets exported or Ability loader changes. The generator
must continue to report incomplete identity rather than substituting raw Ult
content or relaxing a threshold.

An independent serialization issue was found: a generated status alone could
claim identity_reference_ready even if the production parser rejects an asset or
an unsupported masked role. The profile generator now loads the bundled assets
through the production parser before computing readiness. Unloadable generated
or inherited references retain their generation statistics but are marked
insufficient_evidence/reference_load_failed at profile_load. All four references
must remain usable. The image-free report exporter allowlists these new codes.
Readiness/extraction/privacy/relocation focused checks: 8 passed; Ruff and mypy
(86 files) pass. This is a diagnostic honesty fix, not a relaxation of recognition.

Native strict generation remains terminal-session 33844/PID 12497, now past the
PTS scan and computing references. Existing full pytest remains session 58701,
last observed beyond 80%; it loaded the source before the latest generator changes
and cannot alone certify the final source snapshot. The exploratory E2E remains
session 22968/PID 10486 at 72%. No terminal E2E comparison is available yet.

## Native strict profile 04 completed

The common CLI, with native VideoService PTS/decode (not a cache injection),
completed successfully and produced `outputs/hud_profiles/pi-structural-20261006-04`.
HP training/holdout support=28/28; Weapon=15/14; compound spectator=4/4 from
38/38 observations after the bounded extraction accepted all 12 requested unique
frames. Selected compound source index=66; accepted training indices=60,64,66,68;
accepted holdout indices=59,65,67,69. Minimum accepted compound score is above .90.
All three compound asset hashes exactly match the earlier cached diagnostic;
the production generator reproduces that reference without hardcoded proposal
indices or recording timestamps.

The profile loads HP/Weapon and the compound detector with zero runtime reader
diagnostics, zero absolute asset paths and zero missing assets. A copied profile
directory also loads successfully, and the current production asset validator
confirms the same result. The native run loaded the generator before the latest
readiness-validation helper was added; this helper was therefore checked explicitly
on the completed and relocated outputs. Ability remains unconfigured and the
entire profile's identity_reference_ready remains false. No `.env.local` switch.

Full pytest on the earlier source snapshot completed: **980 passed, 6 skipped,
2305.04 seconds**. Skips are the optional sibling validation pack, optional real
HUD anchor recording and Windows/PowerShell host checks. This is not the final
source check: a new full pytest after sampling/readiness changes is running in
terminal session 86186, log
`outputs/recognition-investigation/final-pytest-after-sampling.log`.
Source changes are now frozen while that suite runs. Ruff, mypy and the current
eight focused checks pass. The exploratory native E2E is still live in session
22968/PID 10486 at 72%; await its actual raw/evaluation outputs before comparing
recognition/safety counts or starting the strict-profile E2E. Goal remains active.

## Contour extraction diagnostic and execution resource check

Hypothesis: the existing Weapon Canny extractor, isolated per Ability scaffold
group before normalization/derivatives, could retain the fixed lower frame more
reliably than the ridge extractor. Frozen proposal: keep the previous lower-frame
support/exclusion bounds, same seven-pixel guard, same recurrence/support/layout
requirements, and same .90 bidirectional scoring. Validation bank: 96 unique real
PTS, excluding all prior pilot/contour/wire/lower-frame experiment timestamps,
48 training and 48 holdout. Result: candidate_count=0, structural_rejected=3,
support_rejected=45; no training candidate, so holdout is not used to choose a
replacement. Reject the new extractor; it remains a private offline diagnostic
and no production recognition code or Ability loader policy is changed.

Resource check: the strict production profile was applied to eight actual frames
with OpenCV threads 1 then 4. Complete signal/anchor-score/anchor-diagnostic outputs
are exactly equal. Elapsed times are 7.101 and 7.464 seconds under concurrent load;
this is not a reliable isolated benchmark. Use the existing one-thread environment
setting for the next E2E to limit competition, without changing sampling, evidence,
thresholds or platform-dependent code. The current native E2E remains live and is
not restarted. Final-source pytest remains live in session 86186/PID 13005.

## Terminal-run comparison prepared

Recomputed the original baseline from its actual raw, evaluation and trace files,
after verifying every file against run_metadata input SHA256 values and requiring
terminal metadata, raw status=complete, schema_valid=true and error_code=null.
Actual baseline: 21/57/4, all 20 negative assertions pass, 3869 observations,
unknown=3867, buy_menu_open=2; each identity role is missing in all 3869 frames,
spectator reference_unavailable=3869, fresh/effective geometry=1/3869 and
insufficient_anchors=3868. Round/HUD-event/visual-event/map-resolved/map-held and
every trace count are zero.

Private `outputs/recognition-investigation/compare_completed_runs.py` now collects
all required counts and assertion transitions, rejecting incomplete outputs,
hash mismatches, changed video/pack/assertion hashes, changed assertion IDs or
unexpected assertion statuses. It does not evaluate or rewrite assertions, and
none of its outputs are consumed by recognition/reference generation. Comparing
the baseline with itself reproduces these actual counts and exactly zero deltas;
that is a comparator check, not a new E2E result. Use it when the live native run
finishes, then inspect regressions/false positives before the strict-profile E2E.

## Integrated incomplete-profile safety probe

The strict native profile was processed through RealHudAnalyzer.observe_frames
using 16 timestamped native-cache samples, starting with the original calibration
frame and including normal/obscured/spectator portions. Effective geometry=16,
fresh geometry=1. HP missing=1, Weapon missing=7, Ability missing=16; live identity
insufficient=16. State counts: unknown=15, spectator_first_person=1, live=0.
Spectator checks: excluded=6, ambiguous=9, present=1. The positive observation is
at 160.003 seconds, a source image already inspected as actual Skye/TRIGGER panel.
This cohort includes the reference neighborhood and is an integration/safety
probe, not an independent holdout or a replacement for full E2E. A repeat preserving
the per-observation timestamps/states reproduces the result. It confirms that
the missing Ability reference remains missing after feature/template/temporal
integration, rather than being filled by a heuristic or carried live state.

The latest full pytest is beyond 58% with no failure output so far. Native E2E
session 22968/PID 10486 remains live at HUD timeline/event finalization; no native
terminal comparison or next-run launch yet. No production source changes in this
continuation. Goal remains active and complete identity readiness remains false.

## Final-source whole-suite check completed

The final-source pytest session 86186 exited successfully: **987 passed, 6 skipped,
1706.90 seconds (28:26)**. No production source/tests changed after this suite
started. The six skips remain the optional sibling validation-pack and real-video
anchor fixtures plus native Windows/PowerShell checks; they do not count as Windows
verification. Ruff and mypy src (86 files) passed on the same source changes.
The source diff fingerprint is recorded in the image-free metrics JSON so that a
later source edit cannot silently retain this whole-suite claim.

The exploratory E2E remains live in session 22968/PID 10486 at 72% (last observed
elapsed 95 minutes, CPU time continuing to increase). Full E2E is not passed or
failed until native outputs and terminal metadata are available. Its default
intensity-only Ability/fixed-icon profile remains exploratory, and cannot qualify
the user's strict value-invariant/compound production requirements. Run the strict
profile next after this terminal result is reviewed. No fabricated data, state,
rounds, events or evaluation counts; goal remains active.

## Geometry rejection statistics

Recomputed the exact original even-index training bank using the unchanged
temporal proposal thresholds (grayscale standard deviation <=12, Canny edge
persistence >=.65, minimum 64 informative pixels and selected standard deviation
>=1). Round timer, HP and Ability each have **zero pixels** satisfying the variance
gate across the full training bank, despite 478/870/3794 persistent edge pixels
respectively. Top match bar has 2984 low-variance pixels, 5889 persistent-edge
pixels, intersection=811 and selected grayscale standard deviation=60.2523.
The new image-free diagnostic records normalized coordinates, dimensions, variance
and edge-persistence quantiles, selected counts/ratio and rejection reason. Holdout
was not used. This explains why only the top candidate survives; it does not
justify raising the variance threshold. Next diagnostic should distinguish
unobservable training regions (flash/blur/overlays) from unstable visible scaffold
using existing observability rules, while preserving separate full holdout checks.


## Exploratory native E2E terminal comparison

The exploratory pi-auto-01 run `20261005T153829Z-f1a6683f` completed with raw
status complete, schema valid and no error: **21 passed / 57 failed / 4 not
evaluated**, unchanged from baseline. Negative assertions: 20 passed, 0 failed;
discontinuity violations: 0. Verified input/output hashes and assertion IDs match.
Adaptive sampling produced 4844 observations versus baseline 3869. States:
unknown=4100, live=160, buy_menu=2, spectator=582. HP/Ability/Weapon identity
missing counts=907/2507/2546; live identity insufficient=3716. Fresh geometry=1,
effective=4844, insufficient anchors=4843. Visual events=5, map resolved/held=0.
No assertion improved or regressed. Unknown rates are 84.64% versus 99.95%; counts
alone are not directly comparable because the native sampler adds observations.

The one round package is explicitly an incomplete observed fragment, with no
round-start or round-end HUD event and unknown round metadata. It is not a detected
complete round. The production fragment builder was not changed. This candidate
is not adopted: its Ability intensity reference and fixed-icon spectator method
do not satisfy the user's value-invariant/compound requirements. Recognition
coverage is diagnostic only, not a verified production improvement.

Strict native E2E for pi-structural-04 started in session 91607, wrapper PID14327,
analyzer PID14352, run `20261005T173033Z-b71846e0`. The incomplete profile cannot
satisfy live identity because Ability remains missing. No result is claimed while
the analyzer is running. The environment's selected profile remains unchanged.

## Geometry training presence filtering diagnostics

Existing observability criteria retain all 32 training timer/top/Ability crops
and 31 HP crops; this does not produce timer/HP/Ability candidates. The hypothesis
that these criteria remove the disruptive training frames is rejected.

A separate geometry-only diagnostic proposes pixels using the 28 even training
frames with supported current-frame HP scaffold. It makes no player/live label.
All original 32 training and 32 holdout frames remain in validation. With unchanged
8-training / variance<=12 / persistence>=.65 / 64 pixels / NCC .90 / 3 support /
.80 comparable prevalence gates, top has 837 pixels and supports32/32; Ability
has137 pixels and supports28/28. Timer/HP still have no candidate. These are
unadopted geometry proposals. Identity qualification and localization are not
implied by aligned-crop NCC; a geometry asset cannot become independent identity
evidence. Next: inspect dynamic overlap and runtime localization before adoption.


Production detect_anchors, with original search windows and .90 threshold,
locates the HP-filtered top candidate64/64 and Ability56/64 (28 train/28 held),
with zero accepted offsets greater than2 pixels. However the Ability137-pixel
mask contains key captions and other unqualified content. It is not adopted;
correct localization does not establish value invariance or independent identity.
The next frozen diagnostic enlarges padding around the same four physical
pedestal contours to preserve their sloping ends under the existing derivative
guard, excludes availability fill and key captions before normalization, and
uses a new128-frame cached bank excluding all prior Ability diagnostic samples.
All four groups, .90 bidirectional similarity, structural gates and train/holdout
support requirements remain unchanged. Production code is unchanged.


Padded-contour probe completed without a candidate: training64, holdout64,
candidate_count50, structural_rejected58 (including initial seed rejections),
support_rejected6, holdout_rejected0, reason=scaffold_evidence_insufficient.
Holdout was not evaluated. Larger padding did not establish supported structural
arrangement under the original gates. A training-only per-candidate gate audit
is running to distinguish inadequate spatial arrangement from inadequate edge
support; no production source change or threshold adjustment is justified yet.


Training-only gate audit reproduces all50 padded contour candidate rejections.
All50 pass line support and spatial spread but fail both nonparallel and separated
layout, hence arrangement. The representative mask has346 pixels, density.02237,
self-score1, seven lines, six components, spread(.9367,.4857); only one occupancy
row and four cells exceed the existing .02 occupancy gate. This is not insufficient
NCC or std. Do not lower the arrangement gate to admit parallel pedestal lines.

A new diagnostic freezes two normal Ability-symbol contour groups below charge
counts and above pedestal fills. It uses the existing value-invariant ridge
matcher, not raw symbol intensities, with all structural and independent support
gates unchanged, on96 new cached observations excluding all previous Ability
probe samples. Agent-specific shape is allowed to reject other agents; no agent
classification or values are inferred. No production or environment change yet.


The symbol-contour diagnostic passes the unchanged gates (training22/48,
holdout25/48, mask1068 pixels, group populations619/449, all structural gates
true). It is still **not adopted**: visual inspection of the selected training
reference finds a numeric count in the upper-right edge of the third symbol's
support group. Even if the final edge mask omits that digit, it participates in
normalization and therefore cannot qualify value invariance. A new frozen exclusion
rectangle (source pixels1038,979..1056,997) removes it before ridge extraction.
Revalidate with a fresh96-frame bank excluding the previous symbol bank as well;
do not alter thresholds, support or use the previous holdout for selection.


## Value-excluded Ability symbol candidate

Fresh96-frame validation passes: training21/48, holdout22/48, mask979 pixels,
groups532/447, all original structural gates true, .90 bidirectional matching and
original support/prevalence unchanged. Selected reference and mask visually
inspect as two separated Ability symbol contours with the numeric corner zeroed.
Randomizing **every excluded pixel** on all96 source crops changes scores by
exactly0; removing either group on43 accepted observations gives0 for all86
controls. Constant/random texture controls14 produce0 accepted (max.18254).
Excluded pixels are zero in the saved reference. These controls supplement the
real heldout support and do not replace native E2E or establish false-positive
rates across independent recordings.

Change: permit Ability to use the existing value-invariant matcher with independent
mask and two-to-four support groups in the common production loader; continue to
reject intensity/oriented/Weapon-consensus fallback and thresholds below.90.
All reference structure and per-group matching gates remain identical. Include
Ability's numeric generation diagnostics in the existing privacy allowlist.
Added loader regression checks cover both groups, missing/corrupt support assets,
unauthorized matchers and below-.90 threshold. Ruff/mypy passed. The earlier987-pass
whole suite belongs to the prior source fingerprint; rerun full suite after this
source change. Native common-CLI generation05 is now running with the frozen
Ability region spec and inherited strict04 HP/Weapon/compound assets. It must
pass generation and production loading before complete identity readiness can
be claimed. Strict E2E04 continues on its prior incomplete profile.


## Native complete profile05 generated and relocated

The common production CLI completed successfully and published
`outputs/hud_profiles/pi-structural-20261006-05/hud_layout.json` with
**identity_reference_ready=true**. Ability regenerated from the original native64
sampling bank with training17/32, holdout18/32 and .90 threshold; HP/Weapon assets
are inherited byte-for-byte from validated strict04, whose training/heldout
supports were28/28 and15/14. Compound spectator was regenerated with38/38 samples,
support4/4 and the same strict04 hashes. All four independent reference roles
load through production; no reader diagnostics. All18 referenced assets are
relative and readable; no absolute or missing asset. Copying the full directory
elsewhere preserves successful loading and the production fingerprint exactly.

Native Ability reference/mask were visually inspected: two separate symbols,
numeric corner zeroed. Reproduced generation supports17/18 on the same actual64
native cache; randomizing all excluded pixels changes scores by0. Removing each
support group on35 accepted observations gives0 across70 controls. These controls
are generated-reference verification, not a second independent heldout cohort.
The fresh96-frame symbol experiment separately supports21/22 without relaxing
criteria. Synthetic contrast gains/biases maintain scores>=.9514.

Same16 native-cache integration samples now yield unknown14/live1/spectator1,
versus strict04 unknown15/live0/spectator1. The live observation is115.003 seconds;
spectator160.003 remains spectator. Identity missing HP1/Weapon7/Ability10;
live insuff13, effective geometry16/fresh1/retained15. Spectator checked excluded6,
ambiguous9, present1. This small cohort includes calibration/reference neighborhoods
and is not independent holdout or native E2E. Profile readiness does not establish
E2E failure reduction or broad false-positive coverage. Agent-specific symbol
shapes intentionally leave other agents/variants unknown. Environment unchanged.

Ruff/mypy passed after the Ability loader change; focused tests and the new whole
pytest continue without failure output. The prior987-pass result is superseded
for the latest source. Strict04 native E2E remains live; compare its terminal
results before running complete strict05 E2E. Goal remains active.


The115.003-second live-positive full source frame was visually inspected: normal
player first-person HUD and weapon, no spectator portrait/panel, no buy menu or
remote view. A floating teammate name in the world is not a spectator panel;
the compound detector still requires portrait/text/boundary/relative layout.
This single reviewed positive does not establish an exhaustive false-positive rate.


Latest focused regressions completed:53 passed,0 failed in1026.98 seconds.
The tests cover the common Ability loader/value matcher, generation/readiness,
asset rejection, privacy export and existing auto-profile diagnostics. Full pytest
session84547 continues; strict04 E2E has reached50% adaptive HUD resampling.
The four-reference regeneration stage is achieved, but native complete-profile
E2E and whole-suite verification remain required before recognition adoption.


## Correction: profile05 is readable but not value-invariance-qualified

Additional original even-training counter-cell inspection reveals two-digit
cooldown values (e.g.35/29/24/19/14/12) extending left of the narrow1038..1056
exclusion. Some digit pixels therefore still participate in normalization even
though the selected PNG/mask do not visibly display a count. The earlier claim
of complete value exclusion was too broad. **Profile05 is not adopted and does
not complete the user's strict identity generation stage.** Its technical
identity_reference_ready=true means assets are readable, not that every semantic
exclusion is proven; preserve that native output and mark qualification false
in this audit, rather than rewriting generated evidence.

Freeze the full counter cell to source pixels1018,971..1056,1000 (its right end
is the support group's right boundary). This excludes the count before all
normalization/derivatives, including all observed training digits. Validate on a
fresh96-frame bank (.71 interval offset), excluding the prior .13 bank too. No
threshold, support, structure gate, loader or environment change. Whole tests
remain valid for the unchanged production source. The eventual native profile06
must use this corrected frozen configuration.


Full-counter-cell candidate on the new independent sampling bank passed unchanged
criteria: training20/48, holdout22/48. Selected training reference/mask show the
entire upper-right count cell excluded, retaining two distinct symbol contours.
Common native CLI regeneration06 started in session27722 from validated04 assets
with the new frozen counter-cell configuration. Profile05 is retained only as a
rejected diagnostic; do not use it for the next production/E2E candidate. Whole
pytest and strict04 E2E continue; no source changes after the full-suite launch.


## Qualified native profile06 complete

Native CLI06 completed successfully: technical readiness true and full counter
cell exclusion independently verified. Ability training18/32, holdout18/32;
HP/Weapon inherit validated04 assets; compound spectator38/38 support4/4. No
fixed-icon detector; runtime reference is PanelReference v2. Reader diagnostics0,
relative assets18, missing/absolute assets0; relocation preserves the production
fingerprint. Native counter-cell support array is entirely zero in source pixel
cell1018,971..1064,1000 (the support group ends at1056). Randomizing all excluded
pixels on64 native crops changes scores by0; removing either group on36 accepted
observations yields0 in72 controls. Saved excluded reference pixels are zero.
Native reference/mask visually inspect as two separated symbol contours with
the entire count corner excluded. No thresholds/support/structure gates lowered.

Same16-frame integration probe: unknown14, live1 (115.003), spectator1 (160.003),
geometry effective16/fresh1/retained15, HP/Ability/Weapon missing1/10/7, identity
insufficient13, spectator excluded6/ambiguous9/present1. This is an integration
cohort including calibration neighborhoods, not independent holdout or E2E.
The115.003 source image already inspected as actual normal first-person HUD;
the160.003 source image already inspected as actual compound spectator panel.
The requested strict reference-regeneration stage is now achieved. Recognition
adoption still requires whole-suite completion and native complete-profile E2E.


## Latest-source whole regression complete

Full pytest session84547 completed exit0: **996 passed,6 skipped,2068.44 seconds
(34:28)**. Same source fingerprint180bee3a42fa690b19641f150d1dead9143ee702766849a6176a08e621584335
as at suite launch; all later changes were private profile configuration/scripts
or audit docs. Ruff and mypy86 source files also pass. Skips remain optional
external fixtures and native Windows/PowerShell host checks; Windows is untested.
The earlier987-pass suite is historical;996-pass is current. No source edits are
needed for the broader counter-cell configuration. Strict06 regeneration and
portable current-frame reference verification are complete; native recognition
improvement remains unclaimed pending its E2E.


Complete-profile E2E06 is now queued in private orchestration session78875,
waiting for strict04 terminal metadata. It compares actual strict04 native
outputs with baseline, verifies hashes/schema/completion and refuses launch on
negative/discontinuity or assertion regression. It also checks unchanged source
fingerprint against the996-pass suite and every verified06 asset hash, plus the
compound-v2/no-icon configuration. Only then does it invoke the existing standard
run_dataset_case.py for match_001 with06. Shared exports remain serial; separate
native run output is selected using actual launch UTC time. Queue status and
terminal comparisons are private JSON; no recognition/evaluation or assertions
are changed, and no profile is adopted by the queue. Goal remains active.


## Post-generation residual Weapon diagnosis

Revalidated both live strict04 process14352 and queued06 process16670; neither
is terminal and no run was restarted. Previous turn was progress (native06 full
reference generation, qualification and996-pass full suite), not a blocker.
Read the current goal and Git state before continuing.

On the same16 native-cache integration samples, consensus_score's existing
per-slot diagnostics separate7 Weapon rejects into5 unobservable and2 observable
but contradictory. Raw crops for all7 were visually inspected. At0.036,5.003,
25.003,85.003,145.003 no readable ammo slot UI is present (85 is heavily blurred);
contrast std is below5. At45.003 and65.003 ammo glyphs exist but bright weapon
background/blur disrupts cap/neck/stem evidence: minimum scores.69834/.35630,
with all slots above pixel-contrast observability gates. Do not equate sufficient
pixel contrast with valid HUD presence, drop critical slots, or lower .90 to
force these observations positive. This does not currently justify a mask
change; keep rejected states unknown. All observations/scores are diagnostic
only, not a heldout/E2E improvement claim. The candidate sidecar has no explicit
value readers; timer/score fallback OCR exists, while strict HP requires a full
0..9 alphabet and cannot be supplied only100. Diagnose state-specific evidence
and actual reader returns before adding any downstream event heuristic.


## Timer reader diagnosis and interrupted-run recovery

Problem: profile sidecar readers are empty, but the production analyzer does
attempt default numeric OCR for timer/scores. Actual existing-reader calls on
six training frames all return `tesseract_unavailable`: executable lookup fails.
This is an unavailable optional dependency, not evidence that OCR failed to
recognize visible digits. No dependency was installed during active E2E, so its
runtime environment remains consistent. Do not infer round events from clock
values or supply a partial alphabet.

Separate private timer proposal bank:128 distinct native-cache PTS samples,
even64 training/odd64 heldout, excluding the original64 generator samples.
Numeric field925,27..1000,67 was frozen from original even training pictures.
Training-only representatives were visually labelled, without validation-pack
expected values. Existing production normalization and NCC.90 were used.
Single-reference training qualification requires min3/.80 comparable support.
Digits3/7/8 fail:12/16 (.75),5/7 (.71429),2/3 (.66667); other seven
classes pass. Complete alphabet is rejected before holdout use. No timer
profile, state or event change was made. Images stay in ignored local outputs;
only counts, geometry and reasons are shared.

Recovery: missing strict04/queue PIDs were verified with process listing and
missing terminal outputs, not inferred from elapsed time. No fake exit code or
result was written to that run. The obsolete waiting queue is recorded as
interrupted. A detached private runner revalidated the996-pass source SHA,
relative profile fingerprint, compound-panel policy and all18 asset hashes,
then launched the unchanged standard E2E on profile06. Its completed result will
be compared to the original baseline with identical video/pack/assertions and
output-hash checks. This is a new profile evaluation, not a restart of an
apparently live process. No source, tests, assertions or environment selection
changed in this diagnostic/recovery step.


## Isolated OCR recovery experiment and portable timer candidate07

Problem: default timer/scores OCR dependency is absent on Pi. Downloaded the
Ubuntu repository's Tesseract5.3.4, English data and required libraries into
ignored local outputs using apt package verification; extracted with dpkg-deb.
No system package install, current process environment/PATH change, or production
code branch was made. Package SHA256 values are retained for reproduction.
Existing production TesseractDigitsReader with an explicit diagnostic executable
returns correct timer text above.96 on5/6 training fields; one is rejected.
The original wide layout ROI supplies no accepted timer on this cohort. Numeric
field925,27..1000,67 was frozen from original even training pixels before holdout.

Holdout:64 odd samples in the disjoint128-frame bank, native decoded images.
All64 visible clock values were manually transcribed from pixels before running
OCR; predictions and validation-pack expectations were not used as labels.
Existing SegmentedDigitsReader with empty glyph templates, timer_mmss grammar,
PSM7 and no white-threshold preprocessing uses the same production loader and
SubregionReader. At unchanged uncrosschecked value acceptance.85:51 correct,
13 unknown,0 accepted wrong. At the unchanged shared timer fact confidence.90:
48 correct,16 unknown,0 wrong. Three correct values at.866..887 remain below fact
eligibility; no confidence remapping occurs. One wrong OCR return is rejected by
low confidence. This is a single-recording diagnostic, not an E2E improvement or
an identity/round-boundary claim. NCC.90 identity references are unchanged.

Candidate07 copies native06 unchanged and adds only the existing portable
round_timer reader configuration. It names executable `tesseract`, uses relative
identity assets, and introduces no Pi runtime path to profile data. All18
inherited reference hashes match; layout hash and identity/anchor configuration
are equal. Relocated fingerprint is equal; production reader diagnostics are
empty. Eighteen real non-timer numeric/score region controls have0 accepted
clock values. Controls are a bounded stress set, not prevalence validation.
Candidate07 is not adopted and has no native E2E result. Keep profile06's current
run unchanged. Before candidate07 E2E, account for the existing score OCR
fallbacks that also become available when the runtime is placed on PATH; inspect
their actual values rather than claiming a timer-only environment effect.

Current verified wait: detached runner17549, wrapper17558 and analyzer17578 are
live; analyzer advanced to HUD Pass A analysis and CPU time increased. Native06
run remains `20261005T191132Z-66e9aff2`. Source fingerprint is still the996-pass
fingerprint180bee3a42fa690b19641f150d1dead9143ee702766849a6176a08e621584335.
No new source/test edit was made, so that suite remains applicable. No failure
reduction is claimed, no blocker is present, and the main goal remains active.


## Default score fallback impact and serial candidate07 evaluation

Previous goal turn was progress: isolated runtime recovery, blind timer holdout
verification and portable candidate07 generation. It was not a blocker. This
turn reread the goal, current Git state, native logs and process evidence.

Pixel transcription was frozen before score OCR on16 uniformly spaced odd
holdout samples. Actual ally/enemy score crops gave32 default-reader calls;
all32 were rejected by existing acceptance/normalization,0 accepted wrong and
0 accepted correct. This confirms no accepted score changes on this small
cohort when Tesseract becomes available, not a whole-video guarantee. Do not
force these scores or alter their acceptance confidence. Numeric clock grammar
and value-reader confidence remain distinct from NCC identity requirements.

Candidate07 standard E2E is now queued behind the running profile06 using a
private detached runner. It waits for the preceding runner's terminal status,
then validates native output hashes and video/pack/assertion equality. Any
negative failure, discontinuity violation or previously passing assertion
regression stops the queue for review. Before launch it rechecks the996-pass
source fingerprint, profile fingerprint, compound spectator policy, all18
identity assets and five runtime binary/language/library SHA256 values. The
Tesseract PATH/library/data environment is supplied only to the new E2E child;
profile06 and .env.local are unchanged. Reader configuration still uses generic
`tesseract` executable naming; runtime binaries stay ignored and host-specific,
while the same JSON and production reader are used on Windows with its installed
runtime. Windows remains unverified.

Only one native E2E runs at a time. The next run will compare against both the
original baseline and its immediate predecessor. No timer value becomes actor
identity, no boundary is synthesized, and no assertion/expected result changes.
Both active profile06 analyzer17578 and waiting candidate07 runner18231 were
verified live; analyzer CPU time increased. Source/test fingerprint remains
180bee3a42fa690b19641f150d1dead9143ee702766849a6176a08e621584335.
The waiting-only queue was replaced once to use explicit terminal status rather
than relying on PID disappearance (which can retain a zombie); no analysis run
was restarted. Main goal remains active; E2E failure reduction is unverified.


## Residual compound-panel ambiguity, no policy change

Previous turn made progress by checking score fallback impact and preparing a
serial candidate07 native evaluation. Current06 analyzer17578 and waiting07
runner18231 remain live; no duplicate native run or source change was made.

On the same16 integration samples, production compound detect_panel and its
existing component diagnostics reproduce6 excluded,9 ambiguous and1 present.
This cohort is not an independent holdout or native E2E result. Three samples
have all HP/Ability/Weapon roles supported: one is live with all panel unsigned
coverages0, and two remain UNKNOWN only because compound exclusion is ambiguous.
For those two, unsigned boundary coverage is.14620..15205, portrait.13809..14568,
and text0..13262. Oriented positive scores are0..05766; absence cannot be derived
from failed positive matching. All observability checks pass. Mandatory reference
pixel counts are boundary171, portrait659, text935; expected relative layout and
shared pose remain checked.

The raw lower-left crops were visually inspected: two ambiguous crops show
ordinary floor/wall/teammate scene texture and no visible spectator panel; the
excluded comparison is also ordinary scene; the positive comparison shows the
portrait, adjacent player/switch text and boundary. Ordinary scene edges intersect
frozen component positions enough to exceed the existing.10 unsigned-coverage
absence limit. This explains a coverage limitation without demonstrating a safe
policy fix. Raising that limit or substituting oriented positive failure as
absence would also weaken handling of partial/displaced/different-avatar panels.
Keep those frames UNKNOWN. No state, identity requirement, threshold, reference
asset or profile was changed. Images and per-frame values stay local; only
aggregate scores/counts/coordinates/reasons are shared.


## Prepared fresh current-frame live audit

Previous turn was a verified wait: actual native analyzer17578 remained runnable
and CPU time increased. Current turn revalidated the goal, Git state and both
active/waiting processes. No analysis was restarted or marked blocked.

A private read-only audit now replays common production detect_signals on every
cached native live observation after terminal raw/evaluation/trace hashes and
layout hash are verified. It requires all three identity roles plus explicit
checked=true/panel_present=false spectator exclusion on each image. Missing,
unreadable or conflicting decoded pixels at the same PTS abort rather than
selecting a convenient frame. Profile fingerprint and decoded pixel SHA values
stay in local evidence. The audit emits no states/events and changes no assets.

The saved16-frame integration cohort exercises this audit: its single live
observation reproduces all current-frame gates (1 passed/0 failed), same-PTS pixel
content agrees, and reader diagnostics are empty. This is preparation evidence,
not a terminal native06 audit or independent semantic ground truth. Actual native
live frames must still be replayed and visually reviewed after output completion;
identity replay alone cannot prove absence of all menu/remote/spectator errors.
Current06 remains in HUD Pass A; CPU time reached31 minutes. Waiting07 is live.
Source fingerprint and the996-pass suite are unchanged; no failure reduction
claim or environment profile adoption is made.

### Native06 completion audit queue

The detached local audit queue (PID 19534) waits for native06 terminal validation, verifies the tested source diff hash, and replays production identity checks for every native live observation. It verifies cached decoded-frame hashes and prepares contact sheets of every live frame, with 40 frames per page, for semantic review. This queue does not change recognition, profiles, assertions, or the active run. Replay success and semantic false-positive review remain unproven until the corresponding outputs and images are inspected. All image artifacts remain local under ignored outputs.

### Portable native06 bundle

The local archive `outputs/hud_profiles/pi-structural-20261006-06.zip` contains layout, templates sidecar, all 18 relative reference assets, and a hash manifest (21 files, 437309 bytes). After extraction into a separate temporary directory, every file hash matched and the production loader returned no reader diagnostics; the profile fingerprint remained `3859de5c439346df8d916522bead980a6246f07e0d38c8e2d70b2e24d285b745`. Archive SHA-256: `9a7cc1dfe6527969bfdbb110c2ee7b50ff41aa96e08bceba118517418203b46f`. This is local portability evidence only; Windows runtime and final E2E results remain unverified. Neither the running profile nor recognition code was changed.

### Native06 evaluation and comparison recovery

Problem: the private comparator assumed one failure reason per failed assertion. Evidence: `GT-R1-SNAP-475` has two independently reported field failures, while the official evaluator counts `len(failures)`. Change: compare failure-list count and multiset against per-assertion details, retaining status, uniqueness, schema, output hash and input comparability checks. Native reports, pack, expected values and production source were not changed. Before21/57/4; after22/56/4 by assertion, with57 native failure reasons in both. No passed assertions regressed. The all-live replay must still finish and semantic review remains pending. Profile07 standard E2E was started after the original queued process terminated on this local comparison error; profile06 analysis was not rerun.

### Native06 initial semantic review

Eight uniformly spaced native live observations were inspected as local image previews. No spectator portrait panel was visible in this subset. Two reviewed frames showed buy-phase and combat-report overlays, while both native `state_flags` arrays were empty. This identifies a concrete remaining state-specific coverage gap; it does not establish semantic safety for all589 live observations. The all-live fresh replay remains running and full semantic review is pending. No recognition change was made from this partial review.

### Report header training-only rejection

The native 06 sidecar has no `report_header_detector`, so the existing production static-header witness cannot emit the combat-report flag. A private candidate used only the immutable left/right damage column headers, excluding portraits, names, report values and ability rows. At NCC 0.90 it matched 5/10 independently annotated training-positive frames and 0/22 training-negative frames. Its 50% support fails the unchanged minimum 80% rule. Holdout was not inspected or used, no active profile was changed, and no production branch or threshold was changed. Remaining variation requires a better structural reference; the missing flag is not evidence of player death or a round boundary.
