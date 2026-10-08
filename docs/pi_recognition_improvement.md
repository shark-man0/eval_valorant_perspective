# Pi real-video recognition investigation (2026-10-06 JST)

<!-- CURRENT_STATUS_START -->
Profiles08 and isolated11 completed standard native E2E: **23 passed / 55 failed / 4 not evaluated**, evaluator failure-reasons56. Complete terminal output hashes/schema/null processing error verified. Both improve baseline21/57/4 on `GT-R1-SNAP-705` and `GT-R1-COMBAT-REPORT`; no baseline PASS regressed. Negative assertion failures/not-evaluated and discontinuity violations0. Profile11 versus08 has no assertion-status change.

08 (`20261006T063210Z-3ecd1ba6`) has4559 observations: unknown3940/live455/buy-menu1/Spectator163. Isolated11 (`20261006T063149Z-cc009d82`) has4634: unknown3715/live455/buy-menu301/Spectator163. Sampling differs; count changes alone are not accuracy evidence. Fresh geometry1 in each; effective4559/4634, insufficient4558/4633. Each has one boundary-incomplete fragment, detected start/end0, HUD/Visual events0 and resolved maps0.

All455 live and163 Spectator frames in both completed runs match completed semantic reviews at identical PTS and decoded pixels. Report-visible live0; all455 live freshly replay all three independent structural roles plus explicit checked Spectator absence. All301 isolated11 menu positives visually reviewed and freshly replay both static witnesses at NCC>=0.90, failures0. Unowned player-value leaks0 in reviewed Spectator/menu frames. Known external-camera transitions2 remain incorrectly classified as Spectator-first-person; camera subtype qualification is incomplete. Unknown frames, global geometry correctness, stale/world-state safety and full-video numeric accuracy are not established by these positive reviews. Profile08's single weak-heuristic menu classification is a previously reviewed false menu.

The isolated-tested common menu-witness source is applied to production with eight regression cases. Full Ruff and mypy86 pass; full production pytest1004 PASS/6 SKIP/0 FAIL,1376.80s. Production11 attempt01 `20261006T113548Z-414e4682` was interrupted without terminal outputs and is preserved. Production11 attempt02 `20261006T125627Z-ace6cb0d` completed with23 PASS/55 FAIL/4 not evaluated, matching isolated11 on all compared counts and assertion statuses. All terminal output hashes, unchanged inputs/assertions and baseline/08/isolated11 comparisons were independently reverified. Its455 live,301 menu and163 Spectator positives reuse complete reviews only at identical PTS and full decoded-pixel hashes; novel positives0 and unowned player-value leaks0. The known two external-camera subtype errors remain. Sequential candidate12 `20261006T160007Z-6dc502c6` completed23/55/4 with negative failure/NE and discontinuity0. Its runtime configuration is rejected after blind numeric review found five wrong accepted scores. All340 frozen source/test/config resources remain unchanged. Authoritative statuses are `production-profile11-e2e-queue-attempt02-status.json`, `production-profile12-e2e-queue-attempt02-status.json` and `production-attempt02-terminal-review-status.json` under local outputs/recognition-investigation. Production11 and12 terminal hashes are verified; candidate12 output assessment is complete, and its runtime configuration is rejected.

Candidate12 configures only the frozen HP numeric reader beyond11, but its child OCR environment also activates existing timer/score fallback. These actual shared numeric outputs require separate terminal image review. Additional455 owned images with labels frozen before predictions give444 correct/11 unknown/0 wrong at existing acceptance,440/15/0 at strict0.90; native12 owned HP assessment now gives449 correct/11 unknown/0 wrong across460 owned frames (strict0.90:445/15/0), with unowned HP leaks0. Unsafe timer07 and inherited09/10 are not adopted. Additional strict timer single-reference/preprocessing hypotheses failed complete-alphabet training; additional enemy-score holdout49/64 strict supports fails80%; complementary Spectator bank would remove47 existing live exclusions and is rejected. No holdout tuning, threshold reduction or synthetic event/boundary/snapshot occurred. Relative profile assets and common Windows/Pi production format remain intact. Profile/environment adoption is pending, Windows runtime unverified, and the goal remains active.

Candidate13 now adds optional `ocr_fallback_rois` policy in common production code. Missing key preserves legacy timer/ally/enemy fallback; explicit empty list runs configured readers without implicit OCR; invalid values diagnose and disable fallback. Existing identity, NCC, ownership and compound Spectator policies are unchanged. Ten focused regression cases and full Ruff/mypy86 pass. Full updated pytest completed1014 PASS/6 SKIP/0 FAIL in1263.17s, exit0 and log SHA2568bdbe16f1f49b0712e19c5236eebd8330fb3714c88fd864e579181c53444ce43. All341 frozen source/test/config resources are unchanged. Detached validation PID101468 has started the original standard native E2E with13 (`20261006T224429Z-e77952e0`, CLI102342/worker102357); terminal positive/HP/fallback audits remain queued under PID101559. Child-only OCR runtime was verified in the actual worker environment; no host runtime or profile environment was adopted. Profile13 uses exactly12's layout/reader/23 assets plus `ocr_fallback_rois: []`; moved/extracted fingerprint253a571ecff51dd1043ef9469af27df2644f3bc7647581b7919af4e559183511 verified. Native13 qualification pending. Source/test/config resources are frozen during this sequence.
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

### Report-header persistence reference and candidate08

Problem/evidence: all589 native live frames reproduce identity signals, but the independent image review finds134 current frames with a combat report. One also contains a scoreboard. The06 sidecar does not configure the existing static report witness, which is an existing live-identity blocker.

Hypothesis/change: remove temporally varying background pixels from immutable left/right damage column headers. Use only the10 training-positive frames to align the common header pose, build a median reference, retain pixel std<=12 and edge persistence>=0.65, and maintain two spatially independent groups (272/216 masked pixels). At unchanged NCC0.90, training supports10/10 positives and falsely accepts0/22 negatives. Frozen assets support8/8 independent holdout positives, falsely accept0/24 negatives, and pass24 excluded-pixel/independent-group controls. No portraits, names, values, ability rows, expected labels, or timestamps enter the profile specification.

Candidate08 copies06 and adds only the existing `independent_static_header_v1` specification and three relative assets. All18 prior identity/anchor assets remain byte-identical;21 assets load with no diagnostics or missing/absolute paths, and relocation preserves fingerprint. Fingerprint: `c57ad914218e0e90fca678b0df7adecf620dde5b9caf31e0379c6e17ba016f47`. Timer OCR candidate07 remains isolated. No production code or active selection changed, and candidate08 standard E2E is not yet verified. Existing996/6 full-source checks remain applicable to unchanged production source. Report-only replay on all589 reviewed native live frames confirms134/134 actual report panels and0 false detections among455 report-absent frames. The16-frame production integration cohort retains the same primary-state distribution (unknown14/live1/spectator1) and adds six actual report flags (one before, seven after). Its first-frame report flag was confirmed on the enlarged actual frame with a different portrait and report values. Candidate08 standard E2E is queued serially behind07 (detached runner25123), isolated against06, and will compare unchanged video/pack/IDs with both original baseline and06. It remains unadopted pending terminal native E2E and safety review.

The Git HEAD advanced externally to `65a4a7e040795c0fd7de82ce67a59c2084c44d1e` during candidate08 preparation. The exact source/test/E2E-script patch against original tested base `98600a8d571ccc371575063aef92b43aab87878d` still hashes to `180bee3a42fa690b19641f150d1dead9143ee702766849a6176a08e621584335`, proving the tested source content did not change. Candidate07 native E2E remains uninterrupted. Only the idle08 orchestration waiter was intentionally replaced, before it launched any native08 child, to compare against the fixed tested base instead of the mutable Git index. No Git mutation was performed by the agent.

### Independent score-reader diagnostics while native07 is running

Problem/evidence: the original score ROIs contain surrounding HUD edges/background; previous16-frame broad-ROI OCR checks returned32 unknowns. Training-only numeric fields are ally `[803,20,843,65]` and enemy `[1076,20,1116,65]`. Existing raw OCR on eight even training frames gives4/16 correct,12 unknown,0 accepted wrong. The existing white-text extraction setting200 with PSM7 gives8/8 enemy-score reads correct but keeps all eight ally-score reads unknown. PSM10 gives the same result; PSM8 returns16 unknowns and is rejected. No confidence or identity threshold changed.

The PSM7 enemy field and white extraction were frozen before64 independent odd-frame predictions. Pixel transcription was read before predictions: existing value acceptance0.85 yields53 correct/11 unknown/0 wrong; current-frame fact eligibility0.90 yields51 correct/13 unknown/0 wrong. No rounding of the79.6875% strict-fact coverage or promotion of the remaining13 is allowed. Sixteen flat-field and eight random-field controls yield0 accepted false values. These are numeric reader observations, not generated identity references or proof of score stability.

Rejected reference experiment: existing segmented digit templates built from the three observed glyph types and threshold0.90 do not support the wide-field runtime segmentation. A narrower ally field `[803,33,843,68]` plus the exact existing2x/Otsu preprocessing gives a best actual-glyph reference supporting4/8 training frames; the foreground-merged frame remains in the denominator. This50% support fails the unchanged80% rule, so holdout was not used to select or tune this glyph reference, and no glyph profile is adopted. Otsu merges translucent background/plate pixels with digits on some real frames; this is not evidence of an ARM-specific API issue. Unobserved glyphs were not synthesized.

Conclusion/next: enemy numeric evidence can be improved using existing common reader configuration; ally-score evidence is still insufficient for reliable paired-score stability. No score change, round boundary, or event is inferred from that gap. The frozen raw-field/default-ROI comparison completed against the same64 pixel-labelled holdout frames: original default ally ROI64 unknown; original default enemy ROI1 correct/63 unknown. The training-selected raw ally numeric field yields26 correct/38 unknown/0 wrong (25 confidence>=0.90), and raw enemy numeric field22 correct/42 unknown/0 wrong. Combining the raw ally result with the separately frozen white-text enemy result makes23 pairs readable,22 eligible at confidence>=0.90. This is co-observation only, not temporal score stability or a round boundary. The raw ally field also passes24 flat/random controls with0 false accepts. A portable configuration-only score-reader proposal (`portable-score-reader-proposal.json`) uses generic `tesseract`, normalized subregions and the unchanged existing value/fact confidence gates. Per-role selection comes only from the even training results: raw ally1/8 beats white0/8; white enemy8/8 beats raw3/8. PSM7 supports multi-digit text and was retained instead of the single-character variant. No glyph profile, new production source, complete combined HUD profile, active selection, temporal score stability, or round boundary was added. This proposal still needs native E2E and regression/safety comparison after the active07 and queued08 outcomes. Candidates07/08 and their native E2E jobs remain unchanged.


### HP numeric field and Ammo rejection

Problem: the complete structural identity profile has no configured composite HP/Ammo value readers. Existing common `NumericFieldsReader` can provide independent values without feeding them into identity. Training-only HP field is `[575,1002,655,1048]`; current Ammo field `[1262,1002,1325,1046]`; reserve field `[1349,1014,1395,1042]`. All use normalized subregions, unchanged value acceptance0.85/fact eligibility0.90, and existing PSM7 OCR. No observed value becomes an identity template.

HP white-text extraction200 gives seven correct readable even training frames at confidence>=0.90 and abstains on the ambiguous menu frame. Freeze these parameters before64 odd holdout predictions and pixel transcription. Holdout gives55 correct/9 unknown/0 wrong, all55 eligible at confidence>=0.90; three absent and four ambiguous fields yield no false acceptance. Twenty-four flat/random controls give0 false accepts. Raw spectator HP is numeric pixel evidence only: the existing current-frame recording-player ownership gate remains mandatory. The portable configuration-only proposal uses generic `tesseract`; Windows runtime and native E2E remain unverified.

Ammo is rejected: the raw composite field produces0 correct current reads/7 unknown/1 accepted but unscored ambiguous-menu read, while reserve fields generally abstain. Removing reserve from the diagnostic reader still does not recover supported current reads, so weak reserve confidence is not the sole cause. White extraction also fails to support current reads. No Ammo holdout tuning, digit truncation, confidence reduction, profile adoption, or inferred values were used. The existing strict glyph identity criteria remain unchanged. Candidate07 continues its standard native E2E and candidate08 waits serially; neither is modified by these diagnostics.

The16-frame common-production integration uses a local diagnostic composition of report08, frozen timer07, score fields and HP. All21 structural assets are hash-identical to08. Primary states remain unknown14/live1/spectator1. The single owned live observation produces a confidence>=0.90 HP read; all15 unowned observations, including the actual spectator panel, clear HP and its provenance confidence. Unowned HP leak count0. This is limited cohort ownership evidence, not combined-profile native E2E or proof for every video frame. No active profile or queued native job is changed.


### Purchase-phase static-label candidates rejected

Problem: no `buy_phase_template` is configured. Existing temporal enrichment still requires current banner evidence, a known stable score pair and a readable timer; no phase or boundary is inferred from the absence of those inputs. Before predictions, the32 even generation frames were visually labelled: five purchase labels,27 absent labels. The fixed text-only bounds `[750,168,1170,242]` exclude round number and lower purchase instruction. Six training-only actual/median references were compared at NCC0.90. The selected actual reference supports5/5 positives with0/27 false positives.

The first training probe searched the full banner ROI while the diagnostic sidecar used the fixed crop. This inconsistency was found and independently checked without changing the selected reference: identical fixed-crop training still gives5/5 and0/27. Independent odd-frame pixel labels give1/3 supported purchase labels and0/29 false positives. Nine outside-crop mutations leave confidence unchanged; six half-label removals give0 false accepts. Raw NCC on the three positives is approximately0.923/0.853/0.814. Best locations in full-ROI search agree exactly with the fixed crop, so coordinate search does not explain the rejected held frames. The candidate is rejected, not adopted, and thresholds remain unchanged.

A training-only two-group experiment using existing narrow-ridge structural extraction supports1/5 and is rejected before holdout. A separate training-only static persistence mask uses std<=12, edge recurrence>=0.65, at least32 pixels per independent group and per-group NCC0.90; mask groups have1236/1203 pixels. It supports4/5 training positives,0/27 negatives, but the frozen mask supports0/3 held positives and0/29 negatives. Nine excluded-pixel mutations have delta0, and six missing-group controls falsely accept0. The same odd holdout had already been exposed for the rejected raw candidate; neither masks nor parameters were tuned on it, and this is explicitly recorded. This second candidate is also rejected. Existing production loader does not support generic masked static-label groups; no new loader or recognition code was added for an unqualified candidate.

Conclusion: these actual-label references do not yet meet held support. No purchase flag, state, round boundary or event was forced. All diagnostic compositions remain local and unadopted. Native07 has progressed through HUD Pass A and Visual Pass B into high-density HUD resampling; actual analyzer PID22885 is live and queue08 PID25123 still waits. Source/test/E2E-script contents remain identical to the996-pass tested patch. The next reference attempt needs broader training evidence and a demonstrated treatment of translucent background variation, followed by a fresh held cohort rather than tuning these failed held images.


### Portable combined numeric candidate09 prepared

Problem: independently qualified current-frame timer/score/HP reader proposals were not serialized into a complete profile for standard native evaluation. Change: copy candidate08, preserving its layout, identity, anchor, compound spectator and report specifications plus all21 original assets by hash. Add exactly the frozen generic `tesseract` reader configurations from07 and the score/HP proposals. Candidate09 fingerprint is `78c23c4bdb896243f2c1aeb1e35e2c040abe300ec2096ae58447ea68508204fd`, equal to the existing16-frame ownership diagnostic composition. Relocation preserves the fingerprint;21 relative assets exist, no absolute asset paths occur, and the production loader reports no diagnostics. The initial serialization used literal Unicode rather than the prior escaped JSON representation, causing a fingerprint mismatch despite equal parsed configurations; serialization was made byte-identical before claiming fingerprint equality. This was private orchestration only.

Validation: timer holdout51 correct/13 unknown; ally26/38; enemy53/11; HP55/9. Existing per-reader controls total90 with0 false accepts, within the limited control scope. The16-frame composition preserves unknown14/live1/spectator1, clears HP provenance on all15 unowned observations, and reads HP on the single owned observation. No score stability, phase, boundary or event is inferred. Full native09 evaluation and global false-positive safety remain unproven;09 is prepared only, not queued or adopted. Terminal07 and08 comparisons and safety review precede native09 launch. Production source and the996-pass tested patch remain unchanged.


### Fresh purchase-label cohort and held support rejection

Problem/hypothesis: the prior five-positive training cohort may underrepresent translucent background variation. Prepare66 unique actual cached PTS, excluding both original64 generation and numeric128 observation PTS. Training requests use bounded offsets around five prior training proposals plus twelve non-purchase contexts; holdout requests use distinct offsets. Nearest cached sampling errors are recorded, bounded by0.10sec; an initial0.05sec sampling bound could not supply all cached frames and was corrected before labels/predictions. Recognition thresholds are unchanged. Every selected same-PTS decoded-pixel hash agrees across cache copies; no frame or timestamp is synthesized.

Training images were visually labelled before predictions: sixteen visible purchase labels and sixteen absent labels, including menus/scoreboard that interrupt nominal buy windows. No label was inferred from the proposal timestamp. Seventeen actual/median references were compared using the exact production fixed-crop NCC. The training-selected actual reference supports14/16 positives and0/16 negatives at0.90. Reference SHA-256 `f243cea4041e1dd0574c0adeb58170407d2aa74fe1b1c385f2a294dd5e9741be` was frozen before viewing the34 distinct held frames.

Holdout images were then labelled before prediction: nine visible purchase labels and25 absent labels. The frozen reference supports6/9 positives,0/25 false positives, and therefore fails the unchanged80% support rule. The production loader and matcher agree on all34 predictions. Eighteen half-label removals,24 flat/random fields yield0 false accepts; nine outside-crop mutations yield confidence delta0. This fresh candidate is rejected, not tuned on holdout, not adopted, and not added to09. Native07 remains live at its72% timeline/event stage and08 waits serially. No new complete native result is claimed. Purchase-label evidence still needs a better treatment of actual translucent background variation; additional tuning of these failed held images is not justified.


### Ammo word/raw-line OCR modes rejected

Existing composite numeric fields already use a digits-only whitelist. Changing only to the existing multi-digit PSM8 word or PSM13 raw-line OCR, in both raw and white-threshold200 modes, leaves all eight even training Ammo fields unknown. No holdout tuning or confidence reduction follows this failure. HP results in these modes are poorer than the frozen PSM7 white extraction and include accepted ambiguous-menu pixels in raw mode, so the HP proposal is unchanged. Reserve was not read in this current-only experiment; empty reserve summary rows are not observations. No new source or profile selection changed.


### Independent purchase-menu witnesses and candidate10

Problem: full purchase menus remain unknown in reviewed actual frames, while the classifier already requires both `buy_menu_grid_present` and `buy_menu_close_anchor_present`. Investigate current static category headers `[421,112,1497,140]` and close symbol `[1849,25,1889,64]`; exclude prices, stock, weapon names, player names/portraits and HP/Ammo values. These are state-specific witnesses, independent of the three current-frame identity roles.

Training:32 original even frames plus32 fresh training frames were pixel-labelled before predictions. Five actual full menus are positive,59 other contexts negative. Six actual/median candidates per role use the exact fixed-crop existing NCC matcher at0.90. Selected category headers support4/5 and close symbol5/5; compound support4/5,0/59 false accepts. Freeze both asset hashes.

Holdout:32 original odd frames plus34 distinct fresh held frames contain six visually reviewed full menus and60 non-menu contexts. Frozen category headers support5/6 and close symbol6/6; compound5/6,0/60 false accepts. Twelve one-role-removed controls falsely accept0 compound menus. The common production loader/matcher agrees on all66 predictions and reports no diagnostics. One missed menu remains unrecognized; no threshold is reduced or missed witness inferred.

Candidate10 copies09 and adds only the two relative static signal assets/specifications. All21 original assets and identity, anchor, spectator, report and reader specifications are equal by hash/structure;23 assets are relative and readable, no loader diagnostics occur, and relocation preserves fingerprint `16f144c8fefcacfe5cc70652c9be69d49ce2105a8709e48c20b0c4dcfb0a38b2`. Candidate10 standard E2E is neither queued nor verified and the environment selection is unchanged. The source patch remains the same996-pass tested source.

Common-production integration on the existing16 actual frames changes only the independently inspected full-menu observation from unknown to buy_menu_open. Counts change unknown14/live1/spectator1 to unknown13/buy1/live1/spectator1. All flags, value ownership, HP values and HP confidence match the prior09 composition on the same PTS; all15 unowned frames including menu and spectator clear HP provenance. This is limited cohort evidence, not global false-positive/geometry/stale-state safety, a temporal phase transition or a round boundary. Native07 remains live at72% with growing CPU time;08 waits. Their profiles, source and running processes were not changed by this work.


### Candidate10 negative replay on every reviewed native06 live image

Replay the frozen purchase-menu header and close-symbol signals on all589 terminal native06 primary-live frames. Their prior full-frame contact-sheet review found no full buy menu; the completed semantic-review file and its589-row manifest hashes are verified before relying on that label scope. Each replay image matches its decoded-pixel SHA. Both individual roles produce0 false positives and compound purchase-menu false positives remain0 at NCC0.90. Candidate10 fingerprint remains `16f144c8fefcacfe5cc70652c9be69d49ce2105a8709e48c20b0c4dcfb0a38b2`.

This is additional negative coverage on a previously reviewed live-only subset, not new independent holdout reference generation, all5347-frame semantic safety, fresh geometry verification, temporal carryover verification or standard native10 E2E. No source, profile or native outputs changed. Actual07 analyzer22885 remains runnable and CPU time increased to71 minutes;08 waiter25123 remains live. Neither was restarted or treated as terminal from elapsed time alone.


### Frozen purchase-menu signals across every terminal native06 observation

Read-only replay covers all5347 native06 observations after terminal metadata/output hashes and layout bytes are verified. The production cache uses3-decimal PTS formatting; quantization error is bounded at0.5ms and every same-PTS cache choice has identical decoded-pixel SHA. Replay uses exactly the loaded frozen role templates, normalized fixed crop and common NCC matcher at0.90. It emits diagnostics only; no native state, trace, expected label or assertion is rewritten.

Category headers match293 frames; close symbols match334; both match293. All293 were unknown in native06. All eight full-frame contact sheets of the293 compound positives were viewed: every one displays the full purchase menu, with0 observed compound false positives. Manifest and contact-sheet hashes are retained locally. This adds concrete evidence for a state-specific coverage gap and for frozen menu-witness precision on the5347 sampled frames. It does not establish recall on5054 compound-negative frames, whole-video unsampled-frame safety, geometry/stale-state correctness, complete candidate10 classification/ownership behavior, temporal phase transitions, round boundaries or standard native10 E2E improvements. No reference or parameter was tuned using this review.

Runtime-phase inspection clarifies native07's72% log: `_process_frames` emits that progress before final `observe_frames` on the combined frame set, then runs visual analysis and package construction. This wrapper does not emit per-frame progress during that call. Repeated72% alone is not evidence of a stopped process. Actual analyzer22885 remains runnable with growing CPU time; next-run waiter25123 remains live. Neither is restarted solely because the observation interval elapsed.

### 既存購入メニュー判定の誤認とprofile override診断

Problem: native06の購入メニュー判定2件を実フレームで確認すると、いずれも完全な購入メニューではなかった。

Evidence: current-frame decoded hashを照合して確認。candidate10の独立したcategory header / close-X参照は両件ともNCC 0.90を満たさないが、既存の画素heuristicは両役割をtrueとしていた。`detect_signals`は参照不一致時にkeyを返さないため、analyzerのmerge後もheuristicのtrueが残る。close-Xのみ一致した41件も確認し、完全なメニュー35件、開き始めのtransition5件、メニューのない画面1件を記録した。

Hypothesis: configured structural witnessesを現在フレームの判定元として扱い、不一致や参照利用不能時はunknownを明示する必要がある。absenceの証明には使わず、両役割の独立したNCC 0.90一致を購入メニューの根拠とする。

Change / Tests: 診断のみ。実行中の07と待機中の08に使用されるproduction sourceは変更していない。実フレームでfeature reader → template detector → analyzerと同じmergeを再現し、両誤認の残存を確認した。参照生成の成功とstate判定の安全性を分け、candidate10は未採用のまま維持する。

E2E before / after: native06の22 passed / 56 failed / 4 not evaluatedは変更なし。07は実行中、08は07終了待ち。診断をE2E改善として数えない。

Conclusion: 完全なidentity reference生成は成立したが、候補profileの正式採用にはreport exclusionと購入メニュー誤認の解消・標準E2E検証が引き続き必要。詳細はPiローカルの`native06-one-role-menu-review/semantic-review.json`に保存。

### 購入メニューwitness優先の隔離コード検証

Change: ignored outputs内に共通srcの隔離コピーを作成し、`HudTemplateProfile`だけを変更。menu witnessが一つでも設定されている場合、両役割をcurrent-frame unknown / confidence 0で初期化し、独立した参照一致時だけtrueへ更新する。参照欠落、誤ったROI、NCC threshold < 0.90は診断とunknownを返す。設定のない既存profileの挙動は維持。非一致をabsenceとは扱わない。

Tests: 隔離コピーをimportして57 tests passed、Ruff passed、mypy 86 source files passed。新規回帰は非一致、両役割一致、片方欠落、single-role設定、前フレームの証拠持越し、asset欠落、低閾値、誤ROI、未設定profileを確認。実フレームの2件の誤認を除外し、別の実メニュー2件の検出を維持した。実画像はGit共有しない。

E2E / Conclusion: productionへの適用・全体regression・標準実動画E2Eは未実施。実行中07と待機中08のsource fingerprintを維持し、結果確認後に適用を判断する。正式採用もE2E改善の計上も行っていない。差分・hash・検証結果はPiローカルの`menu-witness-prototype/`に保存。

追加の通常認識器composition検証: 隔離コードに同一profile10と既存16実フレームを入力し、unknown 13 / buy_menu_open 1 / live_first_person 1 / spectator_first_person 1を維持した。state・flags・player ownership・HP/confidenceはいずれも元候補から変化0、unowned HP leak 0。これは限定cohortの回帰証拠であり、全動画E2E検証の代替ではない。

固定holdout 66実フレームを隔離コードのfeature reader + template detector +通常mergeで再検証。参照・ROI・thresholdは変更していない。positive 6中5件を検出、negative 60中false positive 0、両役割の一致結果は既存の固定matcher診断と66/66一致した。未検出1件はunknownのまま維持する。geometryがinvalidの場合は既存analyzerが空signalsで分類してunknownにすることもsource確認し、弱い画素判定が参照検証を迂回する経路を増やしていない。適用用回帰テストを整形後に8 tests passed / Ruff passedを確認。本番sourceと標準E2Eは変更なし。

### Geometry: value-isolated feature NCC候補のtraining棄却

Problem / Evidence: raw grayscaleの時間変動が大きく、従来のmasked anchor生成ではHP/Abilityの安定画素が不足する。identityのvalue-invariant支持は、そのままNCC geometryの支持ではない。

Hypothesis / Change: 既存profile06のtraining生成structural referenceとsupport regionsを使用し、値を除外して抽出したbinary ridge特徴をgroupごとのmasked NCCで比較。reference maskの隣接backgroundを同じsupport group内だけに加え、NCCの分散を確保した。候補はPiローカル診断のみでproduction matcher・profileの変更はない。

Tests: original even 32 training framesだけを評価。NCC 0.90でHP 1/32、Ability 4/32。両候補ともminimum support fraction 0.80を満たさずtraining stageで棄却。holdoutは使わず、anchor localizationも未検証。NCC低下やidentity比率によるgeometry証明への置換は行わない。

E2E before / after / Conclusion: native06の22/56/4、fresh geometry 1は変更なし。07は実行中。正規化した構造特徴の単純NCC化だけでは新しいgeometry anchorを提供できない。候補を追加せず、失敗理由とconfidence分布を記録した。

購入メニュー修正のfalse-live回帰確認: geometry校正用の実フレームに続き、誤認2件、別の実メニュー2件、確認済みlive/spectator各1件を含む7 actual framesを同一profile10で通常認識器に通し、現行sourceと隔離sourceを比較した。両sourceともgeometry calibrated。差分は誤認2件のbuy_menu_open → unknownのみ。両件ともcombat report flagを維持し、player ownership false / HP null / HP confidence 0でliveへ昇格しない。その他5件のstate・flags・ownership・HP/confidenceは変化0。実メニュー2件とlive/spectatorを維持した。初期フレーム時刻を仮定した最初のprivate diagnosticは停止し、保存済みobservationの実PTSを使って再実行した。production source・実動画・packは変更なし。全動画E2Eは引き続き未検証。

### profile11: report08から購入メニュー修正だけを検証する候補

Problem / Hypothesis: profile10には未検証のtimer・score・HP数値reader変更も含まれるため、購入メニューの誤認修正の標準E2E効果を個別に評価できる候補が必要。

Change: base08のlayout / anchors / identities / compound spectator / report detector / readers / 21 assetsを完全維持し、training選択済みの独立category-headerとclose-X参照2件だけを追加。23 relative assets、absolute/missing assets 0、loader diagnostics 0、移設後fingerprint一致。fingerprint `94e52fd77d6c2e5555bf257bcce8abf5e8b284e26c139780c9abf2940f3f059d`。追加数値reader設定やOCR runtimeは含まない。

Tests: 同じ7実フレームで元sourceと隔離sourceを比較。誤認2件はbuy_menu_open → unknown、実メニュー2件・live1件・spectator1件を維持。unowned HP leak 0。他の観測は変化0。閾値は0.90、元のtraining/holdout支持と反例controlを維持。

E2E / Conclusion: candidate11は未queued・未採用・Windows未検証。検証済みのmenu witness共通コード修正の本番適用と全体regressionが必要。07/08は既存sourceで続行し、terminal結果を確認してから次の標準実動画E2Eを開始する。プロファイル作成をE2E改善として数えない。

Geometry NCC参照選択の追加確認: identity用の構造比率で選ばれた参照をそのままNCCで評価したことが低支持の原因かを、trainingだけで検証した。各役割につき既存参照・training feature median・32 actual training referencesの計34候補を比較。NCC 0.90、support mask、feature extractionは固定し、最大training支持の候補を選択した。HP/Abilityともfeature medianが最良だが支持は7/32 (21.875%)で、minimum support fraction 0.80を満たさない。参照を替えるだけでも新geometry anchorは成立しないためtraining stageで棄却。holdout、production matcher、profile、実動画、packの変更なし。局所的な支持改善をgeometry成功やE2E改善として計上しない。

隔離した共通menu witness修正のHUD回帰検証: `test_hud*.py`全22ファイル、calibration diagnostics、追加menu witness regressionsの計24ファイルを実行し、309 passed / 0 failed、992.49秒、exit 0で完了。実行前にimport元が隔離srcであることをassertし、終了後に本番source・隔離sourceのhash維持を確認した。Ruff / mypyおよび実フレームcohortの既存証拠と合わせ、本番適用前の回帰証拠として記録する。全repository pytestと本番コードでの標準実動画E2Eは未完了であり、この結果をそれらの代替にはしない。07/08のsourceは固定したまま。

### Spectator exclusion: 成分別曖昧性の固定参照診断

Problem / Evidence: native06ではspectator exclusion unverifiedがidentity不足の大きな要因。固定profile06を既存64実フレームに適用し、unsigned coverageとoriented positive scoreを成分別に保存した。理由はambiguous 28 / excluded 28 / mismatch 6 / present 2。曖昧28件のcoverage > 0.10はboundary 27、portrait 22、text 15。複数成分が該当するため排他的な件数ではない。

Tests / Interpretation: independent HP/Ability/Weaponの3役割が同じフレームで0.90を満たしたのは14件、そのうちSpect不在未確認は9件。9件をdecoded hash照合付きfull-frame contact sheetで確認すると、Astra first-person外観で可視Spect panelは0件だった。ただしreport表示1件とsmoke表示3件も含み、全件をlive/world-trustworthyへ昇格させる根拠にはしない。画像レビューをcurrent-frame exclusionの代替にしない。

Change / Conclusion: 診断のみ。absence coverage <= 0.10、mandatory portrait/text/boundary、shared relative pose、positive score >= 0.90、whole-ROI vetoを維持する。単なるpositive不一致やworld-edge衝突から不在を宣言しない。新参照生成・mask pruning・production変更は行っていない。boundary以外も曖昧性に寄与するため、boundaryだけの緩和では解決できない。

E2E before / after: native06の22/56/4は変更なし。07は稼働中、保存済みunique PTSは5426件（06は5347件）。これはキャッシュ件数の診断で、完了後のnative observation countではない。


### Native06 spectator 全件 semantic audit

- Problem: panel-positive evidence だけで `spectator_first_person` を確定しており、camera subtype の独立証拠がない。
- Evidence: terminal output/hash と同一PTS decode hashを検証した216件・6ページを全件レビュー。観戦パネル216件、first-person camera確認214件、外部camera遷移2件（native indices 5344/5346）。Combat reportは216件、full buy menuは0件。player固有値漏洩は0件。
- Contract: layoutはspectator_iconをpositive ROIとし、HP/Abilityをnegative_or_changed ROIとしている。classifierはpanel-positiveを直接first-person subtypeへ変換する。Visual specではSpectator/unknownともtarget mechanicsを抑制する。
- Conclusion: spectator exclusionは維持できるが、216件すべてのfirst-person subtype正解は主張しない。camera-mode witnessの独立したtraining/holdout検証が必要。死亡eventや所有権を推測で生成しない。
- Change/Tests/E2E: private診断と統計のみ。production/native出力は変更せず、E2E 22 passed / 56 failed / 4 not evaluated、negative failures 0のまま。07実行中、08待機をプロセス実体で再確認。


### Menu witness prototype: full regression started

HUD関連309 PASSを確認した隔離copyについて、全 `tests/` と提案8件のmenu-witness回帰テストを開始。import先のprivate source実体をassertし、productionとのPython source差分がtemplates.pyのみであることを開始時に確認。OpenCV 1 thread、nice +10で実行中。結果未確定であり、全suite PASS・production適用・native E2E改善はまだ主張しない。07 analyzer/08 queueのプロセス実体は稼働を確認し、再起動やsource変更は行っていない。

Full regression起動の初回はroot sys.path不足により `scripts` importのcollection error 23件でexit 2。初回logを保全し、runnerにrepo rootを追加、private sourceを優先するimport guardを維持して再実行。production/test期待値の修正なし。再実行プロセスの実体とrunning statusを確認。結果は未確定。


### Identity reference pose specificity: training / holdout diagnostic

- Problem/Hypothesis: 構造identityの一致が、位置ずれにも残る場合はgeometry localizationの根拠として不十分。既存HP/Ability参照の位置識別性を診断。
- Evidence: original even32 training / odd32 holdout（decode hash重複0）、固定17 poses（center、8/16 pxの8方向）、既存oriented score0.90・mask・support groupsを維持。各cohortのoff-pose 1024比較で一致0。center supportは両cohortともHP28/32、Ability18/32。
- Conclusion: 試した位置ずれの識別性は確認できたが、NCC anchor品質、任意shift/scale、full-video recall、fresh geometryは未検証。NCC0.90とminimum3 anchorsを維持。参照/profile/source/geometry acceptance変更なし。
- E2E before/after: 22/56/4のまま。07稼働、08待機。隔離menu prototype全suiteは進行中で、結果未確定。


### Smoothed value-isolated NCC geometry hypothesis: rejected

- Hypothesis: 二値ridgeの圧縮揺れがNCCを低下させている。既存feature orientationで使う3x3 sigma0.6 Gaussianを、value-isolated binary featureに固定適用し、excluded regionsを再度zero化。
- Evidence: original32 trainingのみ。既存参照、training median、32実training featureの計34候補から最大supportを選択。NCC0.90、mask、per-group minimum64 pixels/std1、minimum3/0.80 supportは維持。HP15/32（46.875%）、Ability17/32（53.125%）。
- Conclusion: unconditional cohortのtraining supportで棄却。独立にlabelしたvisible-HUD subsetのconditional qualificationは未実施であり、そのsubsetの全方式失敗は主張しない。holdout非使用、追加parameter tuningなし、anchor/profile/production変更なし。
- Tests/E2E: private診断terminal exit0。隔離menu prototypeの全repository pytestとnative07は進行、08待機。最新完了native06は22/56/4、negative failures0のまま。


### Spectator camera subtype: existing current-frame role evidence replay

- Problem: native06のSpectator panel-positive 216件のうち、外部camera遷移2件をfirst-person subtypeとしている。既存3role参照の再利用可能性を診断。
- Evidence: 全216件の同一decoded pixel hashを確認し、共通production matcherでcurrent-frame再評価。一人称視覚確認214件ではHP211、Ability0、Weapon/Ammo197件が支持。外部camera遷移2件は3roleとも0。
- Conclusion: 既存Ability参照を万能のSpectator camera witnessとして再利用する案は棄却（正しい一人称214件を除外する）。HP/Weapon不一致はcamera mode/deathのpositive証拠ではない。agent-neutralで独立したcamera evidenceのtraining/holdout検証が必要。spectator panel/exclusionは維持し、missing structureから既知state/eventへ推定しない。
- Change/Tests/E2E: private診断exit0のみ。source/profile/native出力変更なし。最新完了22/56/4、negative failures0。07/08と全回帰テストは既存プロセスを維持。


### Profile11 portable candidate bundle

- Artifact: `outputs/hud_profiles/pi-structural-20261006-11.zip`（457265 bytes、26 files：layout/sidecar/23 relative assets/manifest）。SHA256 `2daf9560962459e0a4569d783550a249e523cb3dd8deb31af7f19e3685204bcb`。
- Verification: ZIP integrity、展開後全25 content hashes一致、同一fingerprint `94e52fd77d6c2e5555bf257bcce8abf5e8b284e26c139780c9abf2940f3f059d`、reader diagnostics0を確認。
- Requirement: manifestにcandidate-only/未採用/native E2E未検証/Windows実機未検証と、必須menu witness common-source patchのhashを明記。profileデータのみではweak heuristic残存によるfalse buyを修正できない。
- Status: productionや実行中07/待機08への適用なし。全repository回帰テストは既存プロセスで進行中。


### Isolated common-code native E2E preparation

- Problem: 07と待機08が使用するproductionを変更せず、menu witness source修正の実動画検証を準備する。
- Change: ignored outputs配下へcommon source/標準scripts/tests/config/schemas/datasetsをcopy。差分は提案templates.pyのみ。他379ファイルのhash一致を確認。runnerやassertion/expectedの変更なし。
- Verification: 標準runner `--check-environment` exit0、Python3.12/headless imports/git/ffmpeg/ffprobe ready。元動画/Validation Packを絶対パスで使い、独立outputを要求する準備。
- Status: 全repository回帰テストPASSが必要。実動画解析は未起動・未queue・未検証。production変更なし。これはproduction適用後の最終検証完了を主張するものではない。


### Isolated profile11 native E2E queue

全repository suiteの完了を待つqueueを起動し、PID51915の実体とwaiting statusを確認。1004 PASS/6 SKIP、test process終端、隔離workspaceとtest済みsource/resource hashes、profile全25 content hashes/fingerprint、元動画SHA/Validation Pack fingerprintを起動直前に要求。不一致やregression failureならstop-requires-reviewとし、再起動しない。標準runner/実動画/pack/assertionは変更せず、独立outputでbaseline/native06と比較する。08完了後の比較とsemantic quality reviewが必要。production適用と適用後の必須checks/final native検証は未完了。


### Native07 terminal and prototype whole regression

- Native07: verified complete/schema-valid/error-null;22/56/4, failure-reasons57, negative/discontinuity0. No improved or regressed assertion versus06. Sampling5426 versus5347 prevents treating added live/Spectator counts alone as accuracy gains. Latest semantic review remains pending.
- Prototype regression:1001 PASS/9 SKIP in1635.82s, supplemental external-pack nodes3 PASS in6.67s; unique1004 PASS/6 optional SKIP. Initial11 queue stopped before launching because it correctly rejected the unexpected skip scope. Original stopped-state/log preserved. A verified coverage certificate now requires both logs, exact3 node IDs and identical source hash.
- Native11 launched from isolated common-code workspace after all gates;08 also launched after07 terminal. production has not been changed or adopted.


### Native07 live semantic review: reuse guarded by exact current frame

- Evidence: native07 all594 live frames were matched to exact3-decimal cached PTS (maximum0.5ms quantization), and every duplicate decode hash agreed. All589 prior reviewed frames reappeared with same PTS and identical decoded pixels. The prior reviewed manifest hash was verified before reuse.
- New review: remaining5 full-frame images viewed; three independent common-code role matches and explicitly checked spectator absence replayed from each current image. No visible report/Spectator/remote/full buy-menu/expanded-map among these5.
- Conclusion: all594 live semantic reviews accounted for without re-reviewing unchanged images. Existing134 report-visible frames (one also scoreboard) remain quality blockers. No world visibility/global geometry/stale carryover proof, no state/output/profile/source edits, and no adoption. Native07 assertion counts remain22/56/4.


### Native07 Spectator semantic review

All233 Spectator observations audited using exact cached3-decimal PTS and decoded-pixel hashes. All216 prior reviewed frames reused only after same-PTS pixel equality and prior-manifest hash checks;17 new full-frame images viewed. Each new frame independently replayed explicit checked/present Spectator evidence. All233 retain cleared player-specific values with HP confidence0. Visually supported spectator panels233, first-person camera231, existing external-camera transitions2 (native5423/5425), combat report233. No new external-camera transition among17. The two subtype errors remain; do not report233 correct first-person classifications or adopt based on counts. Source/profile/native outputs unchanged.


### Native07 buy-menu positives: prior false positives retained

All2 primary-buy observations match prior visually reviewed native06 false-menu frames at samePTS with identical decoded-pixel hashes; all cache copies agreed. Prior reviewed-manifest hash verified before reuse. Actual full menus0, false-menu classifications2, novel false-menu frames0, player-specific HUD valid=false. No state/output/source edits. Native07 positive-state semantic accounting now covers594 live +233 Spectator +2 buy observations. It confirms rather than clears the known quality blockers: report-visible live134, camera subtype transitions2, false menus2. Native11 evaluates configured current-frame witness overrides; no improvement/adoption is claimed before terminal semantic checks.


### Native07 timer jump semantic review: candidate rejected

- Problem: the initial64-frame blind timer holdout had51 correct/13 unknown at existing0.85 acceptance, but that cohort does not establish whole-run numeric accuracy.
- Evidence: among4070 readable and1356 unknown timers,97 readable confidence values are below0.90. A fixed diagnostic rule selected7 adjacent pairs (gap at most0.25s, absolute jump above2s). Both blind gallery pages were visually reviewed;14 pixel transcriptions preserved privately. Four pairs contain one incorrect reading each, while3 pairs contain actual on-screen changes. No actual change is interpreted as a round boundary.
- Diagnosis: all4 incorrect frames replay through the same production reader with identical values/confidences. Raw OCR produces format-valid minute-digit substitutions; seconds components match. Three errors are below0.90, one is0.95371284. Raising acceptance to0.90 alone cannot qualify this candidate. Review SHA256 `3276995a8510900606187a0eb5bd1064fb418c2afb23e385525c8fe42ddbb595`.
- Conclusion: profile07 timer and inherited09/10 timer are unqualified;08/11 do not include this timer candidate. No speculative punctuation/digit correction, clamp, inferred phase/boundary, source/profile/native-output modification, or holdout tuning. Four errors are established in a targeted diagnostic subset; global error count/accuracy remains unknown.
- Tests/E2E: exact-frame reader replay4/4, loader diagnostics0; latest completed native remains22/56/4, negative failures0. Report-only08 and isolated common-code11 remain live.


### Geometry visible-training subset hypothesis: rejected

- Problem: original unconditional NCC support could be reduced by absent/blurred HUD frames; conditional visibility had not been tested.
- Evidence: all4 blind bottom-HUD training pages visually reviewed before computing conditional scores. Independent pixel labels identify28 visible structural scaffolds,3 absent and1 blurred/ambiguous frame. The Ability subset includes25 configured-Astra and3 other-agent scaffolds. No values or matcher scores determine these labels.
- Change: private diagnostic only. Keep prior value isolation, fixed masks,3x3 sigma0.6 representation, per-group minimum64/std1, NCC0.90 and minimum3/0.80. First condition existing34 frozen candidates on visual visibility; then reconstruct medians solely from independently visible training frames.
- Result: both fixed-candidate conditioning and visible medians support HP15/28 (53.57%), Ability17/28 (60.71%). Configured-Astra Ability median17/25 (68%). Absent false accepts0/3 and blurred accepts0/1. All fail training qualification; no holdout inspected, profile/anchors/source unchanged. Diagnostic SHA256 `f960b9c630b662521b500cc0cdf6fe611911df61999c8824ba6163e59078749f`.
- Conclusion: missing/other-agent contamination alone does not explain this NCC hypothesis failure. Reject these candidates; do not lower thresholds or repeatedly tune the same holdout. This does not reject every possible feature representation or assert geometry is globally safe.08/11 native processes and source freeze remain unchanged.


### Ability training group observability

- Evidence: unchanged production feature score decomposed per group on the32 original training frames, guarded by the prior independent visual labels and decoded-pixel hashes. Configured-Astra visible25, supported18, unsupported7. Limiting first group4 / third-slot group3; nine group failures each for oriented recall and precision below0.90. Group decomposition reproduces every full score exactly.
- Diagnosis: the saved reference/mask image was visually inspected and predominantly contains first/third Ability icon contours. Training-only lower-container coordinate review proposes separating fixed outlines from mutable fill/stock and key-label cells. This is a new reference hypothesis, not established improvement.
- Change/Tests/E2E: ignored private diagnostics only, holdout not used for group analysis. No threshold, production/profile/native-output change; original08 and isolated11 remain active. Diagnostic SHA256 `b2fcfb62c1f32edcab0cba2f67307104e7f2e006bea279cc3427a74199b52d80`.


### Ability fixed lower-container reference hypothesis: rejected before holdout

- Hypothesis: avoid Ability icon state appearance by using separated first/third lower fixed container outlines. Support boxes742,1027..840,1067 and971,1027..1065,1067; mutable fill/stock and key-label cells excluded before feature extraction. All bounds fixed from visually inspected training coordinates.
- Evidence: unchanged value-isolated features and three-pixel derivative guard retain at least32 pixels in each group on20/25 visibly present configured-Astra training frames. This eligibility count is not identity support or qualification.
- Generator: unchanged shared scaffold_reference returns no reference. Training-only proposal stages: group-population rejection7, initial minimum-support rejection7, structural-arrangement rejection18. All18 arrangement candidates fail line support/nonparallel/separated-layout/edge-density conditions; edge self-support additionally fails1. Holdout was not reached or evaluated.
- Observability: ignored local instrumented function adds rejection records only. Asserted exact equality of all original core statistics and generator outcome; original production function/source/profile untouched. Diagnostic SHA256 `0f9c06dc61663ab2ccc52c368aac61ed8b3bb68752b37a5cbc46aba5b111ce7a`.
- Conclusion: reject this fixed-container hypothesis under existing anti-false-positive gates. Do not convert feature population into a qualified reference, relax arrangement/density thresholds, or reuse mutable gauge values.08/11 continue their existing real-video runs; latest completed native remains22/56/4 with negative failures0.


### Spectator exclusion training edge collisions

- Evidence: all4 original training observations with independent three-role identity support but unverified Spectator exclusion were decomposed into raw Canny edges, dilated unsigned matches and frozen boundary/portrait/text labels. Gallery reviewed, with one additional actual Spectator-present training control. Same decoded-pixel hashes and detector reasons verified.
- Visual findings: the4 panel-absent crops contain wall trim, first-person arm/hand, world character body/weapon and foreground ability effects, or character legs/slanted floor edges overlapping expected component coordinates. Actual control visibly contains portrait/adjacent text/boundary and remains checked-present.
- Diagnosis: reference assets are available. Raw world/foreground edge overlap explains unsigned absence ambiguity in these4 cases. Low oriented positive scores do not prove absence; pruning expected labels or raising0.10 would change the safety policy rather than establish stronger evidence.
- Change/Tests/E2E: diagnostic only, original training subset, no holdout/source/profile/native changes, no global false-positive/absence claim. Review SHA256 `74d479d129b1b160313202fb2432feabe78d035ffdd494445ad05ebb662834af`. Existing08/11 native processes remain live; terminal comparisons and semantic reviews remain pending.


## Production menu witness application and gated native validation

Problem: configured static menu references left weak texture candidates active on nonmatches. Evidence: isolated11 retains all455 live and163 Spectator pixels, removes the known08 false menu and recognizes301 visually verified full-menu frames. Both independent static witnesses pass NCC>=0.90 in all301 current-frame replays; player-specific value leaks0. Hypothesis/change: configured menu witnesses must replace their weak fallback candidates with unknown until each current-frame reference matches. The isolated-native-tested templates.py was copied exactly into production and eight meaningful regression cases were added. Thresholds, identity/Spectator policy, original video/pack/assertions are unchanged. Ruff all and mypy86 pass. Live455 replay is complete with455 PASS/0 FAIL. Full production pytest is running; the gated standard production E2E queue will verify their terminal success and unchanged source/profile/assets before launch, and compare with baseline,08 and isolated11 after completion. Production profile/environment adoption and global safety remain unverified; existing two camera-subtype errors, geometry insufficiency and absent round boundaries remain unresolved. Windows runtime remains unverified.


## HP-only candidate12, prepared without changing the active production validation

Problem: qualified player-owned frames still lack numeric HP readings. Evidence: the previously frozen HP field reader has55 correct/9 unknown/0 wrong on64 disjoint holdout frames and0 false accepts on24 flat/random controls; this is field-reading evidence, not global accuracy or player attribution. Change: copy profile11 and add only the frozen player_hp_armor HP reader. Layout bytes, all23 relative assets and all non-reader specifications remain identical; no new timer/score/ammo reader, identity or ownership change. NCC/glyph threshold0.90 remains unchanged. Loader diagnostics0, missing/absolute assets0 and relocation fingerprint equal. Candidate fingerprint `fdeda023d9ffe0028a73083e9f6feb891d674928dca262b91f06acd3933220ff`. Seven reviewed real frames replayed through the common production analyzer: all state/flags/ownership unchanged, six unowned frames retain cleared HP/confidence0, and one player-owned reading matches an independently viewed pixel transcription with confidence>=0.90. This is one-frame numeric accuracy evidence, not a global guarantee. This separate private candidate is not adopted or queued for native E2E; production11 regression/evidence/E2E gates remain unchanged. No numeric pixels are used for identity.

## HP candidate12: additional blind owned-frame diagnostic

Problem: the separately qualified HP reader still needs numeric-pixel checks on all455 already verified native11 player-owned frames before a new native candidate run.
Evidence: all eight image sheets were reviewed before OCR predictions. Pixel labels453 readable/2 ambiguous were frozen with manifest and sheet hashes. This fixed cohort overlaps prior diagnostics and is not a new independent holdout.
Change: replay the unchanged profile12 HP field reader on this additional cohort; parameters, identity references, ownership gate and production sources stay fixed. Values and images remain in ignored local outputs; only counts and hashes are shared.
Tests/E2E: completed all455 unchanged-reader replays: existing acceptance444 correct/11 unknown/0 wrong; confidence >=0.90 gives440 correct/15 unknown/0 wrong. Both ambiguous fields are unknown; ambiguous false accepts0. No reader diagnostics. Native12 is not yet E2E-qualified or queued; production11 full pytest and subsequent standard native E2E remain independent gates. Replay SHA256: a8cce0aa996f766f854f5871d95e0712baf7b259c8864592be40c5f49492c0b7.

## Production verification gate passed; sequential HP candidate E2E queued

Common-source full regression completed1004 PASS/6 SKIP/0 FAIL (1376.80 seconds), log SHA256 59f005dab74e87d671def41f6db65e1c6a9721fe41bb837b22a821717e750de7. Required Ruff all and mypy86 were rechecked successfully immediately before production11 standard native launch `20261006T113548Z-414e4682`. Source snapshot SHA256 8f6f99cd0652a9f80aa1527f91a014d39b143916367feff31753faa8f37948fb. No source/profile/adoption changes during the run. Candidate12 waits for the terminal production11 run and unchanged sources/assets, verified output/input hashes, negative failures/not-evaluated0, discontinuity0 and no baseline PASS regression before its separate standard native run. It uses the generic common `tesseract` reader with local external OCR runtime supplied only through the child environment. No Pi recognition branch, active environment adoption, timer/score/ammo reader or generated event/boundary is added.

The candidate12 local transfer archive has26 files/23 required relative assets, 457432 bytes, SHA256 22d848693b8c425553746861079d1250db31807000917bc6f23c8d086a18cb5f. Extraction hashes and relocated fingerprint match; reader construction diagnostics0. External Tesseract/English data and the verified common menu patch are required separately. Archive validation is not Windows runtime or native E2E qualification.

## Remaining unknown cluster: fixed blind diagnostic cohort prepared

Prepared64 uniform-rank unknown observations from verified terminal isolated11 after excluding the prior128 numeric-diagnostic timestamps. Exact PTS/cache quantization and same-PTS pixel hashes verified. This is additional diagnostic taxonomy, not a new independent generation holdout or global false-unknown estimate. The first8 full-frame/HUD/panel crops were visually reviewed before per-role scores: visible HP/Ability scaffold in8, panel visually absent8, one combat-report overlay and one Astral projection view. Both are distinctions to retain rather than force into live. Remaining56 pending blind review. An initial unreviewed montage overlapped panel and bottom crops; v2 separates those panes and is the authoritative review artifact. Production source/profiles/active E2E inputs unchanged.

## Unknown64 blind taxonomy and current-frame evidence: completed

All16 sheets/all64 full-frame and HUD/panel panes reviewed before per-role predictions. Scene counts: Astra world-view appearance46, Astral projection9, external death camera2, full buy menu1, Spectator first-person5 and Spectator external death camera1. Display appearance labels do not establish machine player attribution or independent structural qualification. Frozen label SHA256 0eee4e862890ba35a5b22e76b2dc31939eccbf900428ef34d99a00ad891a69ce.

Unchanged common feature/template witnesses measured on all64; scope is current-frame/nominal geometry, without native temporal context or a global false-unknown claim. Among46 Astra world-view appearances, HP38/Ability19/Weapon23 supported; all3 roles7. Identity reasons: competing-view8, Spectator exclusion unverified22, structure insufficient16. Spectator visually present6 are conservatively ambiguous6, with no machine player promotion. Knife10 have Weapon support0, pistol18 support7 and rifle16 support16. Lack of an observable ammo-slot structure in knife/projection/cast views must not be filled by other roles. Group-level diagnosis is running for the existing Ability and Weapon scores; no templates, thresholds, production logic or native states changed. Replay SHA256 11ff57300138a35b5fef3d9f464de74ea0e71c5b07527d57d20eca12a2adb2dd.

Unknown46 exact group decomposition completed: all group scores reproduce the frozen current-frame role support. Pistol Weapon11 failures comprise2 frames with an unobservable slot group and9 with all groups observable but NCC below0.90 (limiting group1 in4, group3 in7). Knife10 failures have9 unobservable and1 observable-but-contradictory; cast2 are unobservable. Rifle16 pass all groups. Ability27 failures limit group1 in12/group2 in15. No missing-slot fallback or lowered NCC is justified. Diagnostic SHA256 5248c62606881e873e6221c45e5971f6f6f525538f2b1518166d76786722d8c5. A separate training-only consensus-reference re-encoding probe uses the even32 samples with immutable masks/allowed regions/critical-slot requirements; holdout is not used for candidate selection.

### Weapon fixed-mask training consensus re-encoding: rejected

Problem/Evidence: nine blind-labelled pistol world-view samples fail Weapon similarity despite observable critical slots. Hypothesis: refitting contrast consensus on newer training backgrounds can improve those matches without changing masks, value exclusions or all-slot requirements. Change: compare existing reference, the production encoder mean of all15 qualifying even-training pistol/rifle appearances, and15 singleton encodings. Candidate choice uses even32 only; no odd holdout loaded. Result: existing reference remains best,10/15 support; required minimum3/80%=12. All17 candidates fail training qualification. No new asset exported, no profile/source modification, no holdout tuning, and native11/queued12 unchanged. Conclusion: simple reference re-encoding cannot solve this cohort; investigate persistent-slot feature/reference quality rather than lower NCC or ignore a critical group. Diagnostic SHA256 eee3bc9ec449dc7e8f12da4c596c5f3b503a8cde000ec8f756794024adf90483.

### Weapon pistol training position hypothesis: rejected

Problem: training-only fixed-mask consensus refitting did not improve similarity. Hypothesis: a common ammo-slot position offset beyond the runtime1px search accounts for pistol rejection. Evidence/Change: all8 even-training pistol crops compared with unchanged contrast/allowed regions/critical masks; diagnostic feature displacement explored at radius6px without changing native acceptance. Exact radius1 results reproduce the production matcher. Baseline3/8 supported; none of5 failures reaches0.90 even at radius6. Actual crop1265,1005..1389,1066 and slot-mask panes visually inspected: bright first-person glove surfaces and sharp glove boundaries underlie the fixed separator strokes, consistent with contrast contamination; not proof that every full-video failure has that cause.

Conclusion: reject simple position expansion. Runtime search remains1px, NCC0.90 unchanged, all3 slots required, no holdout inspected, no reference/source/profile or E2E input changed. Diagnostic SHA256 60c1d71ea7825dde54d50006902cc22e68034bb1700cc0461109ef3c437126d6. The production11 worker remains live; queued12 awaits terminal verification.

### Shared Weapon persistent-slot regeneration on additional64: generated, then rejected

Problem/Hypothesis: fixed-mask recoding and position expansion failed; shared discovery may identify a cleaner structural support mask. Unchanged production persistent_reference runs on the fixed64 real crops with even32 training/odd32 holdout, original intended/dynamic/neighbor exclusions, NCC0.90 and minimum3/80% gates. Generated3 critical slots; all9 training consensus contributors supported, training10 and holdout15 supported. No numeric-value or matcher-score filtering of the input cohort. This is additional diagnostic data, not fresh independent holdout or full-video qualification.

Frozen candidate comparison: old/new training support12/10, holdout15/15; gains0 and losses2.96 limited controls show0 failures (36 excluded-pixel mutations,36 slot-neighborhood erasures,16 flat,8 random). Erasure includes a feature halo and may affect neighboring slots;30 began with candidate matches and6 were already unmatched. These controls do not prove global false-positive safety or independently intact neighboring groups. Adoption rejected for no gain and two losses, despite generator qualification. No production/profile/E2E-input change or further holdout tuning. Validation SHA256 78d7d0d76df6f35f9f44f8a1ca5a47d3ab2dde9ee6b9aad794be368b454564d3.

### Shared Ability scaffold regeneration on additional64: qualified but no improvement

Problem/Hypothesis: Ability has27 missing supports among46 blind-labelled Astra world-view appearances; new training data may produce more representative structural contours. Unchanged scaffold_reference uses even32 discovery/selection and odd32 qualification, original role/neighbor/value exclusions and structural gates (line/nonparallel/separated layout/density/self-support). Generated2 independent groups,631/430 masked pixels,13/13 training cluster support; training13/holdout15 at0.90. A single training-frozen candidate was compared against old current-frame witnesses on all64 without further tuning. Old/new training13/13 and holdout15/15; gains0/losses0 across all scene categories.

Conclusion: do not adopt or queue another profile for this unchanged coverage. Generation qualification alone does not demonstrate improvement. Additional controls/full regression/native E2E for an unadopted zero-gain candidate are unnecessary; existing production11 and queued12 remain unchanged. No global accuracy or fresh independent holdout claim. Generator SHA256 c5b933a8b090882a0102d6e6c36562c4b9b5a25351658971b3547f400189474b, comparison SHA256 030a48742e53f234d311862d425e7357b5eda5e097350e2b7f3ca4c7d30746c5.

### Unknown Spectator compound components and additional regeneration: rejected

Problem/Evidence: six independently reviewed unknown frames visibly contain a Spectator panel, but the frozen compound witness remains ambiguous. Exact current-frame decomposition on all six plus three previously verified positive controls reproduces detector reasons. Boundary passes0.90 in2/6, portrait0/6 and text4/6; limiting components portrait3/boundary3. All3 positive controls pass. All3 raw/reference-overlay sheets visually reviewed; changed character appearance, measured boundary/background variation and foreground effects are visible. These observations identify local mismatches, not a global cause or proof of absence. Component diagnostic SHA256 ea76020a86c0a207241378c9f4b38742ccc1e7c1572dff998a2c7f3b41430afa.

Hypothesis/Change: run unchanged shared generate_panel_reference on all64 fixed diagnostic crops, even32 training/odd32 holdout, without scene/value/score filtering. No reference generated: candidate_count0, structural_rejected32, portrait proposal support0. All32 holdout proposals skipped; holdout acceptance was not reached. Visually present training panels3 and holdout panels3 do not by themselves qualify a machine reference. Generator diagnostic SHA256 e469a3e2e3f04a2055edab2f02de03904f16a9f9a61f3abe0e4cb80960a69473.

Training-only observability: an ignored in-memory instrumented frameless helper records separator/ridge/glyph/run/pair stages on the three even-training present panels. All original results and core statistics exactly equal the unchanged helper. One has separator candidates but no valid two-row relative layout; another has a valid separator and first text row but lacks a qualifying second compact row; the third has no Hough separator proposal. These samples illustrate measured segmentation/geometry limitations; do not reinterpret visually present text as qualified evidence, weaken brightness/occupancy/layout gates, or prune mandatory components. Diagnostic SHA256 632ebcf5405a5ba03234940222f1ee4264e73efe221f9e7083ca7c67cb58ae4d.

Tests/E2E/Conclusion: reject this additional regeneration attempt before holdout. Existing complete profile11, NCC0.90, minimum3/80%, shared pose radius2 and explicit absence threshold0.10 remain unchanged; no new profile/source/native-input/adoption change. This cohort was already used for diagnostics and is not a fresh independent holdout. Production11 standard native E2E continues with growing worker CPU time; candidate12 waits for its verified terminal result. No new full regression is needed for ignored diagnostics and documentation only.

### Training-centered Spectator neighborhoods: complementary candidate, replacement rejected

Problem/Hypothesis: sparse training present panels fail portrait proposals; nearby real frames may provide correctly segmented boundary/portrait/two-row evidence under different backgrounds. Fix three even-training present-panel centers and offsets -1.5/-1/-0.5/+0.5/+1/+1.5 seconds before opening new pixels or matcher results. Exclude the original64 diagnostic and original generation timestamps; choose18 distinct nearest cache frames within0.15 seconds and freeze even9 training/odd9 holdout. This temporal-neighborhood cohort is not a fresh independent temporal holdout.

Evidence/Change: all6 full-frame/exact-panel sheets/all18 images visually reviewed before generator results were opened. Present14, absent3 external-death views, unobservable1 blurred transition; proximity alone does not imply a present panel. Unchanged shared generator produces a compound candidate with3/9 training and3/9 holdout supports under its existing minimum3/80%-of-training-cluster gate. Portrait remains required, with boundary/text/relative layout; no name, numeric value, state or score filtering. Selected training index10, component edge populations121/1342/756. Generator SHA256 184cd0d1939df897b974f9f44b9f65ef04174e361f59dceefcc038f2df1f8125; blind-label SHA256 13c7ae4c9ba3109c163d7e71c85987de3f5379c17a25ce1371f8e4fb4715e460.

Frozen comparison/Conclusion: on existing unknown64, two additional visually present first-person panel frames become checked-present (odd diagnostic indices59/61), no false positive on57 visually absent frames and no false absence on6 visibly present panels. One existing absent-exclusion gain and two losses. On additional18, present-panel gains6/losses3; no observed false positive or false absence, but previously supported panels at indices6/7/13 become unknown. Reject single-reference replacement for these losses. Complementary-reference storage/detection is not implemented or adopted; do not merge positive components from separate candidates, treat unverified components as absence, or infer camera subtype from panel presence. No native/source/profile/threshold/adoption changes. Existing production11 standard E2E and sequential candidate12 remain the native gates.

Completed broader candidate diagnosis on all455 previously reviewed isolated-native11 live and163 Spectator positives. Same native state, exact PTS and decoded-pixel hashes verified against completed semantic reviews. Candidate checked-present on live0/455, checked-absent408/455, unverified47/455 (mismatch26/ambiguous21). All163 existing Spectator positives are ambiguous under the candidate, with no false absence. A positive union of full compound references would preserve old panel positives, but conservative absence requiring every reference checked-absent would remove47 existing live exclusions. Reject both single replacement and this complementary bank hypothesis for this coverage regression; do not discard its absence checks or merge individual components to preserve coverage. No bank implementation, profile adoption, extra control/full regression/native run for the rejected candidate. Diagnostic SHA256 4fcdc550c1b15601e5fbb94977771270db7b9bb959b5b76695465287521f0d9d. These fixed reviewed positives support a local regression decision, not global false-positive safety or correct camera subtypes.

## Production native interruption and isolated-session attempt02

The production11 attempt `20261006T113548Z-414e4682` was interrupted without terminal raw processing or evaluation artifacts. Observed monitoring-session exit143, then all original queue/native process handles missing; the independent candidate12 queue stopped with production11_handle_missing_without_terminal_result. Last analyzer stage72% (HUD timeline/event finalization). The signal origin is not independently established. This is not a completed recognition result, an assertion regression or an observation-timeout-only restart. Preserve the original output directory and interruption record; no input/expected/native-output changes.

Verified all340 source/test/config resources unchanged and all existing regression/current-frame gates still satisfied. Launch attempt02 queues with portable subprocess.Popen(start_new_session=True), detached stdin and separate persistent logs, outside the observation process group. Original standard E2E command, video, pack, profiles, thresholds and source snapshot unchanged; Ruff all and mypy86 pass again at the queue gate. New production11 standard run `20261006T125627Z-ace6cb0d`; candidate12 waits for its verified terminal comparisons. Both new queue sessions were verified live with their own process groups and parent1. Authoritative current statuses are `production-profile11-e2e-queue-attempt02-status.json` and `production-profile12-e2e-queue-attempt02-status.json`; old status paths describe attempt01 only. No source/profile/environment adoption or full regression rerun for an unchanged source tree. Attempt02 is not E2E-qualified until complete outputs and semantic reviews are verified.

### Attempt02 terminal review queue prepared and verified live

An independent persistent low-priority queue waits for each attempt02 native terminal result, then verifies hashed complete outputs before preparing positive-state visual review. Reuse prior completed labels only for the same native state, exact PTS and identical decoded pixels. Novel frames generate separate pages and remain pending agent review; additional positive states outside the three previously reviewed roles also remain unverified. All unowned player-specific fields must be cleared and explicitly recorded HP confidence must be0; a missing confidence field stops review rather than supplying a default.

For terminal candidate12, a separate private audit compares actual native HP values/confidences with the455 previously frozen blind pixel labels after same-PTS/full decoded-pixel equality. Report correct/unknown/wrong/ambiguous accepts and strict0.90 counts, without rerunning OCR or tuning parameters. New owned pixels require new blind labels; no broad numeric accuracy claim. Prior label/manifest/hash/status invariants verified, helper scripts compiled, queue process session verified live. Status: `production-attempt02-terminal-review-status.json`. Native outputs, original assertions, source/profile and environment adoption unchanged; these private review preparations do not establish native recognition qualification.

## Additional strict timer alphabet training: rejected before holdout

Problem: previously tested raw Tesseract timer has four established high-confidence errors; the earlier strict numeric-glyph alphabet failed classes3/7/8. Hypothesis: additional actual font samples can qualify the existing strict reader without relaxing NCC0.90, class margin0.04 or minimum3/80% comparable-class support.

Sampling/Evidence: select128 distinct previously unused actual cached PTS by a frozen uniform-rank rule; exclude original generation, earlier timer proposals, unknown64, added Spectator-neighborhood and blind HP timestamps. Initial fixed-time-nearest preparation stopped before freezing selections/pixels because no eligible cached PTS existed within its0.20s sampling window at some targets. The replacement rank rule was fixed before opening any selected images; this changes sampling, not a recognition gate. Even64 training/odd64 holdout; all4 training raw-field sheets/all64 training fields were visually transcribed before class predictions. Holdout images not reviewed and all64 holdout proposals skipped. This additional same-video cohort is not a fresh independent temporal holdout.

Change/Tests: an ignored in-memory probe executes the unchanged StrictTimerGlyphReader.read prefix and captures normalized glyphs before classification. Of64 readable training fields,49 have valid strict segmentation,14 fail the foreground-border gate and1 fails exact two-dot separator structure. Unsegmented readable glyphs remain explicitly reported rather than disappearing from coverage. Select one actual training reference per class using all segmented same-class training glyphs and original NCC/support rules. Training supports:0=36/38,1=40/40,2=11/12,3=12/18,4=7/8,5=10/14,6=3/3,7=1/3,8=5/6,9=5/5. Classes3/5/7 fail; no complete alphabet, reader/profile export or holdout matching. Numeric pixels are never identity evidence.

Conclusion: reject this additional single-reference alphabet hypothesis. More training examples improve class8 but do not resolve other shape/segmentation variability. No numeric correction, threshold/gap/border relaxation, inferred event/phase/boundary, source/profile/native-output change, active profile adoption or duplicate full regression. Qualification SHA256 cfa29569f1027a1e7ca3a5beb8526e2311c9f6637013f1be00946816fdcaef64; frozen training-label SHA256 0a706d04167cc1b1c22ee9861dc0dcccc8c95a5142d18e1f48c003e64d47be66. Production11 attempt02 and sequential12/terminal-review queues remain unchanged.

### Fixed-white timer training probe: rejected before holdout

Hypothesis: a fixed white-foreground threshold200, already used for numeric-field diagnostics, may remove background contamination without weakening the strict reader's structural/NCC gates. Use the same64 even-training raw fields and frozen blind labels; no threshold sweep, holdout inspection or production change. The unchanged strict segmentation/normalization prefix accepts50 fields;9 foreground-border and5 exact-two-dot rejections. Comparable-class supports at NCC0.90/minimum3/80%:0=39/39,1=38/41,2=12/12,3=19/19,4=9/9,5=10/14,6=2/2,7=2/2,8=6/6,9=3/6. Classes5/9 fail support and6/7 lack minimum3 examples. Complete alphabet rejected; no full-field predictions, holdout matching, profile export or adoption. Current production strict reader has no white-preprocessing configuration. Diagnostic SHA256 3039b9e1c32209f61fc9e9ae449d5a5bceffcf72bb5c21b32ece16e0e08b6525. Existing full regression and active attempt02 native runs are unchanged; no duplicate regression for rejected private diagnostics.

### Spectator positive HP structure correlation: diagnostic only

Join all163 completed isolated-native11 Spectator semantic reviews to earlier completed216-frame structural replay by exact PTS and decoded-pixel SHA256. First-person161 have HP-structure support158; external-camera transitions2 have support0. Three first-person frames lack support (review indices108/126/127). Verify unchanged HP signal specification, reference/mask/support-region pixels and replay six selected actual current frames with the common value-invariant matcher. All six accepted-confidence/support results reproduce prior production signal outputs. Raw subthreshold NCC differs from published confidence0; both are explicitly recorded, rather than weakening acceptance to reproduce an unavailable confidence. Diagnostic SHA256 f9c40d221759ee4704539fc1ef7cb28e97c23135cf933e5f07bac1618635f02b.

Conclusion: HP support is a candidate correlation, not independently qualified camera projection evidence. Missing HP cannot identify death/external camera, and this already-reviewed cohort is not new training/holdout qualification. No camera gate, production/profile change, owned-value promotion or native-output rewrite. Existing player ownership still requires all three independent current-frame structures plus explicit Spectator exclusion. Attempt02 native11 remains live, currently at dense HUD-change extraction; sequential12 and terminal reviews await verified completion.

### Timer raster-normalization hypothesis: rejected before holdout

Evidence: all15 failed-class/reference tiles visually reviewed. Same-class contours show varying thickness and corner/ridge occupancy; this is consistent with raster/segmentation effects but does not isolate their cause. Training-only morphology diagnostic SHA256 6a0433c49d274e9fed6ee3d100cb32d0f884cd1df874d43097e4c4efc6f7bc5e.

Hypothesis/Change: one fixed INTER_AREA downsample followed by binary threshold128 may reduce nearest-neighbor aliasing. Use unchanged production segmentation prefix, bounding boxes, output size/centering, NCC0.90, class margin0.04 and minimum3/80% comparable-class support on the same64 even-training fields. No threshold/interpolation sweep or holdout use. Class supports:0=35/38,1=35/40,2=12/12,3=15/18,4=6/8,5=10/14,6=3/3,7=1/3,8=6/6,9=5/5. Classes3/8 improve, but4 regresses below80% and5/7 still fail. Reject the complete alphabet before holdout; do not combine preprocessing branches per class or add unsupported variants to preserve coverage. Production has no such normalization configuration, and no source/profile/reference adoption or native-output change occurred. Diagnostic SHA256 8a81a535ee29b3863155fc209e8c8a9dedde36561676ac894c73b801b94c4e90. Existing complete regression and attempt02 native queues remain unchanged.

### Read-only current-frame runtime diagnosis during attempt02

Problem: terminal HUD timeline/event processing has a long interval without new stage messages. Verify live worker CPU growth rather than treating unchanged log progress as termination. Earlier completed isolated11 and standard08 took approximately3h20m from their recorded starts to completed output mtimes; this is historical context, not an ETA.

Evidence: profile current common-code detect_signals once each on three previously reviewed live/Spectator/unknown actual frames, after exact decoded-pixel hash checks. Fixed OpenCV threads1 and lower scheduling priority; current native worker continues concurrently. Elapsed0.803/0.551/0.805s with cProfile overhead. Spectator detect_panel cumulative0.603/0.349/0.608s, including rigid compound component matching0.409/0.334/0.395s. These three samples do not establish global throughput, an end time or recognition accuracy. Diagnostic SHA256 c6abf463511cf87e5a396ebc48b6bda74e56a134fcdd273e214bbcfb4eae774b.

Conclusion: do not restart a live CPU-active native run, weaken/exclude Spectator checks, or label runtime work as recognition improvement. No optimization, recognition/source/profile/native-output change or duplicate full regression. Native11, sequential12 and terminal review queues remain the outstanding gates.

### Additional owned-frame enemy score qualification: rejected

Problem/Hypothesis: existing white-text enemy score configuration had8/8 training successes and53/64 held readable values, but only51/64 strict0.90 facts. Additional verified-owned current-frame pixels may determine whether this frozen reader is suitable for a later numeric-only profile; no new settings are selected from additional predictions.

Sampling/Evidence: freeze128 distinct actual isolated-native11 live observations by uniform eligible rank(index+.37), excluding rounded3 PTS used by the prior score cohort. Every chosen PTS/full decoded-pixel hash matches completed three-role identity plus explicit Spectator-absence replay. Even64 training/odd64 holdout. Existing enemy reader specification is frozen before new pixels: generic tesseract, PSM7, threshold200 white extraction, exact numeric field1076,20..1116,65 and unchanged value acceptance0.85/current-frame fact confidence0.90. All four training sheets are read and labels frozen before training predictions; only after its gate passes are all four holdout sheets read and labels frozen before held predictions. This is additional same-video validation, not independent temporal qualification. Numeric pixels remain excluded from identity evidence.

Tests/Results: training53 correct/11 unknown/0 wrong at existing value acceptance; strict0.90 gives52 correct/12 unknown/0 wrong and meets80% local diagnostic support. Frozen holdout49 correct/15 unknown/0 wrong at both thresholds;49/64=76.5625%, below80%. Reject this reader's additional qualification; no score profile composition/adoption, holdout retuning, inferred score stability/round boundary/event, source/native-output change or further controls/full regression for the rejected proposal. Manifest SHA256 47ee0a6a623545b6d6386415d8218c59f943a5e123870310da0fe823776285f1; training-label SHA256 2fa33e77938468e634b9e63dc2002b48dbd69c5a4c695a3bb6402903a990ae4d; holdout-label SHA256 be0dfb05973c7b7da9e4c5477e7d6eaf000fb742f1cafa0d4b7f9cfbae023bcf. Zero wrong on these128 fields is local evidence, not a full-video accuracy guarantee. Production11 attempt02 remains live; sequential12 and terminal reviews continue waiting for verified completion.

### Candidate12 default numeric fallback exposure and terminal audit gate

Problem/Evidence: candidate12 sidecar explicitly adds only player_hp_armor, but HudFrameAnalyzer constructs the generic digit_ocr_reader and _read_values uses it for unconfigured round_timer/ally_score/enemy_score. The child-only generic Tesseract PATH therefore activates all three existing fallbacks as well as HP. The seven-frame integration and455-image HP audit do not establish default timer/score accuracy. This does not reinstate the rejected narrow timer07 configuration, and broad fallback accuracy must not be inferred from its failures or successes.

Change/Verification: prepare a private terminal-only audit of every actually accepted native shared numeric value. First verify complete output hashes/schema/null error through the existing comparator. Join only exact PTS/full decoded pixels to previously frozen timer64 training and enemy-score128 blind labels; novel accepted fields produce indexed context/field sheets with values and confidence hidden. Actual predictions are written separately for comparison after blind transcription. Record reused correct/wrong, pending labels and accepted-below0.90 separately. No OCR replay, profile mutation, native-output rewrite, inferred stability/boundary or default detector disablement. Helper compiled and checked against completed isolated11: actual accepted fallback fields0, no pages needed; this is not candidate12 qualification or a positive-path coverage test. Check summary SHA256 615359a8bf7f58197e800e7dca942679ac03eec1e30e4b010a39c3729c441765.

A detached low-priority queue waits for verified candidate12 terminal outputs before preparing this audit. Live process/session/parent1 verified. Status path: production12-attempt02-terminal-fallback-review-status.json. New pages remain pending human-agent visual review; no global numeric accuracy or adoption claim even if all reused labels match. Audit helper SHA256 454b32f635d9b466f1f7e2045e811a11ab216aa2aa6d075205cdb65059d3f09a; queue SHA256 ca6cb61f255fa66020b33acd1f78717da6d689baa6b76c91510642c17ea1e048. All340 frozen production/test/config resources remain equal. Production11, sequential12 and previous positive-state/HP review queues continue unchanged.

Terminal numeric audit positive-path smoke: an ignored in-memory limited probe executes the unchanged queued helper on the first three actual accepted timer fields of already-rejected native07. Complete native output hashes verified first; no copied/modified native inputs or outputs. One hidden-prediction context/field sheet visually checked; freeze three pixel transcriptions before loading its separately stored native predictions. All3 match,0 wrong. This checks accepted timer-row extraction, confidence recording, exact PTS/full decoded-pixel mapping, visual crop layout and post-label comparison. It is not a complete native07 audit, a score-positive-path test, restoration of unsafe timer07, candidate12 qualification or general timer accuracy. Original helper and queued digest unchanged; the limited probe marks full blind review incomplete. Smoke review SHA256 010ccdbe48505ae3d25f67decb329aa89dc61a3b30005bf4934b003812d87de2. Candidate12 actual fallback audit remains queued; native11 still live at timeline/event finalization.

## Fixed raw-majority timer training reference rejected

Problem: single-image timer glyph references failed full-alphabet training at unchanged NCC0.90, minimum3 distinct supported frames and80% comparable support. Hypothesis: one fixed majority-pixel reference per class, derived entirely from actual normalized training glyphs, could represent raster variation. The same frozen64 training frames and labels were used; no font drawing, preprocessing mixture, threshold sweep or holdout access.

Evidence: digit3 supports12/18 glyphs (12 distinct frames); digit5 supports10/14 (9 frames); digit7 supports2/3 (2 frames). All three fail80% support and digit7 also fails minimum3 supported frames. Diagnostics SHA256 `3db78b2773a7e0521d9fe970d5f1ba1cd46dbdc5485b1a96bfea68ab88164eb4`.

Conclusion: reject before holdout and complete-reader testing; no profile exported, production changed or further regression/native run required for this rejected local diagnostic. E2E stays at verified production11 23/55/4 while candidate12 native evaluation runs. The64 timer holdout frames remain unused.

## Native12 terminal blind assessment: HP correct, score fallback unsafe

Problem: candidate12 configures HP only, but child Tesseract availability activates existing default timer and score OCR. Evidence: standard native run `20261006T160007Z-6dc502c6` completed23 PASS/55 FAIL/4 NE, failure-reasons55, negative failure/NE0, discontinuity0. Native output hashes/schema/error and11 comparison independently verified; no assertion status improved or regressed against11. Observations4692: unknown3751/live460/menu301/Spectator180. Geometry fresh1/effective4692/insufficient4691; one incomplete fragment, detected boundaries0, HUD/Visual events0, maps0.

All22 novel positives viewed on three full-frame pages: five live,17 Spectator first-person; previous reviews reused only with identical PTS/full pixels. Known two external-camera mis-subtypes persist; positive review does not establish unknown/global geometry/stale-state safety. Native unowned player-specific value leaks0.

Blind labels were frozen before reading native numeric predictions. All460 owned HP outputs:449 correct/11 unknown/0 wrong; strict0.90 gives445/15/0, with four accepted below0.90 under existing reader acceptance. All4232 unowned frames show no HP leak. Actual default timer accepted20/20 correct, including five below0.90; ally score4 correct/1 wrong of5, enemy score2 correct/4 wrong of6. Timer acceptance-only correctness does not qualify recall or round boundaries.

Conclusion: reject current candidate12 runtime due to five accepted score errors; retain evidence that the isolated HP reader works without claiming this runtime safe. No profile/environment adoption, value correction, threshold relaxation or boundary inference. Next step: inspect common numeric fallback configuration so a qualified HP reader can run without silently enabling unqualified score readers, then verify common Windows/Pi behavior and native E2E.

## Explicit profile numeric fallback policy

Problem/evidence: the same child Tesseract runtime that reads HP activates the analyzer's implicit OCR for three unconfigured shared fields. Native12 blind image review finds5 wrong accepted score outputs (4 with confidence>=0.90); raising a threshold would not qualify that route.

Change: optional top-level `ocr_fallback_rois` in schema1.0 template sidecar. Allowed names are `round_timer`, `ally_score`, `enemy_score`. Omitted key retains existing behavior; a list enables fallback only for listed ROIs; empty list uses explicit readers only; malformed list records a profile diagnostic and disables implicit OCR. An explicitly configured/injected reader remains usable regardless of fallback policy. Profile fingerprint already includes the sidecar bytes. No OS branch or threshold/identity change. This prevents unrelated executable availability from expanding a qualified profile's numeric capabilities.

Add `"ocr_fallback_rois": []` beside `schema_version` in a template sidecar to prevent implicit numeric OCR. Keep the complete qualified reader specifications in `readers`; the actual portable13 sidecar contains the previously frozen HP specification. Profile13 copies12's layout and all23 relative assets byte-for-byte; only the fallback list is added. ZIP SHA256 `00dd7eeca0bddcc357d3957bb88f1c31f93dcfdd3526dd00690236eeb31495ba`; relocation/extraction matches fingerprint `253a571ecff51dd1043ef9469af27df2644f3bc7647581b7919af4e559183511`. Windows runtime unverified.

Tests: ten new cases verify HP remains usable, no implicit scores, optional timer-only fallback, explicit score override, legacy fallback and malformed policies. All pass; full Ruff/mypy86 pass. Updated full pytest followed by standard native E2E is queued under `production-profile13-validation-status.json`; terminal positive/HP/fallback review preparation is queued separately. E2E before: verified11 23/55/4; rejected12 23/55/4 with wrong score5. E2E after: pending; no adoption or completion claim.

## Native13 common-analyzer actual-frame integration

Eight cached native12 frames were replayed through the complete common analyzer using actual calibration prefix, profile13 assets and the real generic HP Tesseract subprocess. The five newly reviewed live positives use labels frozen before predictions; three unowned controls are the actual menu, Spectator and initial unknown frames. No injected geometry, identity or state signals.

Results: state,flags,view context and ownership equal native12 on all8; owned HP5/5 correct at confidence>=0.90; unowned HP/confidence leaks0. Wrapped actual fallback reader records0 implicit calls; all timer/score outputs are unknown. Report SHA256 `0b76016f9d9d985419052f4064b3cebc6dd940f40a819f931ec8e3c4bea4fc55`. This integration scope establishes behavior only on these8 frames; full updated pytest and standard native13 E2E remain pending. Frozen341 source/test/config resources verified unchanged.

## Exploratory Report-conditioned additional Spectator presence

The unconditional extra-reference bank was rejected because47 reviewed live frames lose checked absence, and all163 prior Spectator positives become ambiguous. A distinct frozen diagnosis now uses the extra reference only to add presence when an independent current-frame static Report header passesNCC>=0.90 and all compound portrait/text/boundary witnesses pass the unchanged common detector. Original checked presence is retained; the extra reference contributes no absence. On the already examined64 unknown and18 neighborhood images, additional presence2+6 is visually present in every case, with no original presence loss. The47 previously affected reviewed live frames all have an inactive static Report gate. This is evidence to investigate a conditional positive witness, not independent qualification: both cohorts were previously examined, camera subtype remains unqualified, and no production/profile/native output was modified. Disjoint real-frame positive/negative evidence is required before implementation.

## Report-conditioned reference: disjoint training rejection

The conditional-presence rule and all existing reference assets were frozen before new labels/predictions. All previous manifest PTS and decoded-pixel hashes were excluded. New panel windows153–155s(training12 frames) and158–160s(holdout10 frames), plus16 controls per split from0–70s and70–140s, provide54 distinct frames with no previous or split overlap. All five training pages were viewed and labels frozen before matching. Training:0/12 supported panels,16 absent controls with0 false positive,0 false absence. Static Report header passes on all12 positives(.9927–.9953); the frozen extra compound reference remains ambiguous on all12. Training qualification fails at unchanged0.90/minimum3/80%. Holdout26 images remain unread/unpredicted; no candidate adopted or tuning on holdout. A separate existing-generator reference for the newly observed structural panel group may be investigated using training alone before the untouched temporal holdout.

## Separate training-generated compound reference with Report gate

A distinct structural reference was generated by the unchanged existing compound generator from the12 newly labeled training panel frames only; external158–160s holdout was not used for generation. Internal even6 proposals/odd6 validation each support6/6. Frozen conditional presence replay on all training28 frames gives12/12 panel positives and0 false positive across16 absent controls. Reference/condition/threshold/evaluator were frozen before temporal holdout predictions. Five held pages were visually labeled before matching:10 panel positives,15 absent controls and1 unobservable menu-overlay control. The diagnostic additionally rejects checked presence on an unobservable image, introduced before any holdout prediction with no threshold/reference/condition change. Temporal holdout gives10/10 positives,0 false positive and0 unobservable false accept. NCC0.90/minimum3/80% and independent portrait/text/boundary/relative-pose evidence are unchanged. This is same-recording panel-presence qualification, not camera subtype, primary state, ownership, global coverage, independent recording or native E2E qualification. The three standard PNG assets remain local and are not adopted. Existing reviewed live/Spectator/menu side effects must be checked before common-code implementation, which remains frozen during native13.

## Conditional additional panel reference: reviewed-cohort side effects

Frozen witness replay covers455 reviewed live,163 Spectator and301 menu frames, plus64 fixed unknown and18 prior neighborhood frames(1001 total). Profile11 and13 share byte-identical layout and all non-reader/non-OCR-fallback configuration. Same-PTS/full decoded-pixel identity and reviewed labels are checked;455 original current-frame checked-absence proofs are reused from the completed fresh live audit. The independent Report condition is freshly replayed on every frame; original checked Spectator presence is retained and skips the extra reference. The conditional extra reference is inactive on all919 prior positive-state frames, with original presence/absence losses0. Fixed unknown64 gives no extra presence; neighborhood18 gives2 extra presences, both visually labeled Spectator-first-person, with no false presence or additional absence. Known prior external-camera mis-subtypes2 remain; no camera subtype, ownership, state-machine integration or native E2E qualification is claimed. Source remains frozen during native13. A common-code isolated prototype and subsequent production regression/native validation are still required before adoption.

## Isolated common-code positive Report-gated panel variant

A copy of frozen common source adds optional `report_gated_spectator_panel_references`. Every variant requires a valid v2 compound primary reference and independent static Report header, coherent portrait/text/boundary support assets andNCC>=0.90; configured higher thresholds are respected. Invalid entries diagnose and disable the entire optional list. Each current frame first retains primary presence; only independently verified current-frame Report presence can enable the extra compound reference, which contributes presence only. Failed matches cannot add absence, and injected/legacy Report flags cannot replace the independent header check. Current-frame state resets are tested. New12 focused cases plus related modules give75 PASS; changed-file Ruff and module mypy pass. The isolated relative profile has26 assets, fingerprint4680b6eb9ddaedb65998f6e771706c7814b801fd50f9a7665d014138293df2f2, and relocation equality/no diagnostics is verified. Import provenance is explicitly checked because ordinary editable imports otherwise resolve the original root source. Full common analyzer replay of62 actual frames uses a genuine native calibration prefix and actual child HP OCR, with no injected anchors/identity/signals. All22 new panel confirmations occur in the current frame;40 controls retain identical state/flags/view context/values; unowned leaks0,5 prior owned HP controls correct, implicit OCR calls0 for both baseline and variant. This narrow same-video integration does not qualify global camera subtype, map overlays, native full-video counts or Windows runtime. Original341 source/test/config resources remain unchanged and native13 remains active. No production adoption occurred; full production regression and standard native E2E remain required after native13 assessment.

Isolated prototype boundary validation extension: eight additional cases cover malformed/empty variant banks and a current-frame legacy Report pixel-template positive with an independent header negative. The latter retains original checked absence and does not consult the variant. Related focused suite now83 PASS (6.11s), changed-file Ruff PASS. Prototype recognition source and assets are unchanged; therefore the earlier62-frame integration evidence remains applicable to the identical source hash. Original frozen341 resources rehashed unchanged. Production native13 is still running; no standard-native, camera-subtype or Windows qualification is claimed.

### Geometry common rigid translation: rejected on training

Hypothesis: fixed-position group NCC might undercount a qualified structural anchor because the entire HUD scaffold shifts a few pixels. Diagnostic freezes the earlier visible-training medians, masks, isolated ridge representation,3x3 sigma0.6 smoothing andNCC0.90/minimum3/80%; permits one common integer displacement dx/dy in[-2,2] across all support groups, never independent per-group fitting. All32 original training images and prior independent labels are hash-verified. Fixed-position scores exactly reproduce the prior diagnostic within1e-6. Joint translation gives HP15/28, Ability17/28 and configured-Astra Ability17/25, identical accepted counts; absent/ambiguous false accepts0. All candidates fail training. Reject this local rigid-translation explanation; no holdout inspection, threshold/reference/profile/production change or native anchor qualification. Diagnostic SHA256 7396671c7207613991123f164cd9228c9d3af64393bc70bc9b6030afde1cb8f5. Native13 remains the same active run.

### Timer actual-glyph reference bank: insufficient training support

Question: can the existing common reader's multiple-template capability resolve the earlier single-reference alphabet failure without changing segmentation/NCC? Reverify the3 digit7 raw training glyph hashes and all9 NCC comparisons, using only even-training manifest entries and frozen blind labels. They occur in3 distinct frames; each supports only itself atNCC0.90. No candidate meets minimum3 supported frames, so an individually supported raw reference bank is empty for7. Exporting all3 exemplars would bypass the existing support gate. Reject this specific raw-candidate bank before holdout, full-reader/profile export or production edits. Other representations and new disjoint training are not ruled out. Diagnostic SHA256 c5b13af3e615b2addf5d2746618044ffc693e4b76bc2fd80a43f33c8f9209449. Native13 continues unchanged.


## Production13 terminal assessment

Standard native run20261006T224429Z-e77952e0 completed:23 PASS/55 FAIL/4 NE; negative failures/not evaluated and discontinuity violations0, no prior PASS regression against baseline/production11/rejected12.4634 observations:unknown3715/live455/menu301/Spect163. All919 positive frames reuse frozen visual labels only at identical PTS and full decoded pixels; known2 external-camera mis-subtypes remain, so camera/global accuracy is not qualified. Actual HP455 owned:444 correct/11 unknown/0 wrong, strict0.90:440/15/0;4 accepted below0.90 reflect unchanged existing reader policy.4179 unowned values leak0. Actual implicit timer/score accepts0. Fresh geometry1/effective4634/insufficient4633; one incomplete fragment, no detected start/end boundaries, HUD/visual events or resolved maps.341 frozen resources/profile fingerprint unchanged at terminal. Full regression1014 PASS/6 SKIP/0 FAIL, Ruff and mypy pass. Windows runtime remains unverified; no environment adoption. Terminal raw SHA256 0fcb422bf583d58a3f9d38facc4279d062c052de383f761d6dd8b1957748285c.


## Candidate14: Report-gated compound panel references

Problem/Evidence: primary compound reference lacks a qualified second layout; unconditional extra bank harms47 prior live exclusions. Disjoint training12/holdout10 panel positives, training16/holdout15 absent and1 unobservable controls qualify the frozen generator-v2 reference at existing0.90/minimum3/80%. Prior919 positive-frame side-effect check and isolated62-frame full common-analyzer integration preserved controls and ownership.

Change: applied the reviewed isolated common-code prototype exactly to templates.py and added20 routing/validation test cases. Optional relative compound-v2 references require independent current-frame Report header, cannot contribute absence, retain primary presence priority and never promote player ownership. Candidate14 retains explicit HP reader and empty implicit timer/score fallback policy.26 relative assets; profile fingerprint 4680b6eb9ddaedb65998f6e771706c7814b801fd50f9a7665d014138293df2f2. No OS branch, camera policy or threshold change.

Tests/E2E: isolated focused83 PASS; main full Ruff/mypy pass. Main full pytest is running, then the existing standard native command will execute and compare baseline/production11/production13/rejected12.342 source resources are frozen during validation. No native14 result, camera subtype or Windows qualification is claimed yet.

Candidate14 full regression completed:1034 PASS/6 SKIP/0 FAIL in1250.36s; full Ruff/mypy PASS. Pytest log SHA256 6b85e2bfa9cfa9dfa226bc36544d5f46fc8f90022bed3c78f1d3130c0d5b5846. Skips remain optional sibling-pack/video environment and host Windows/PowerShell checks; these skips do not qualify Windows runtime. All342 frozen resources and candidate fingerprint/26 assets reverified unchanged. Standard real-video E2E started at outputs/e2e/match_001/20261007T034919Z-442972cd (CLI114138/worker114155 verified live). Terminal baseline comparison and fresh semantic review remain pending; no native14 accuracy or environment adoption is claimed.

### Timer whole-glyph one-pixel registration: training support still insufficient

While native14 runs with frozen source/profile, examine the same3 hash-verified even-training digit7 glyphs with one common dx/dy in[-1,1] and zero border. One pair improves fromNCC0.8062 to0.9414, but supported-frame counts remain1/2/2 at0.90, below minimum3 and80% class support. No eligible reference exists. Reject this local-registration-only explanation; no holdout, candidate export, reader/profile or production change. Diagnostic SHA256 b83f962c2f23016dd117ddec75b579c733fd67d13a29e19c0fb62fc141487371. The glyph montage shows stroke/normalization differences beyond common translation; their precise cause is not yet qualified.

Long-command observation policy updated following user AGENTS instructions: native14 E2E continues unchanged; kernel pidfd exit notification replaces manual short-interval process/log checks. Existing review coordinator with a5-second status loop is suspended until driver exit, then automatically resumed for the already queued terminal audits. No E2E restart, growing log read, recognition/profile or safety-policy change. Waiter metadata:outputs/recognition-investigation/profile14-terminal-waiter.json; exec session27662.

## Timer-only candidates15/16: full qualification rejected (2026-10-08)

Problem/Evidence: the rejected combined OCR candidate12 included wrong score values; profile13 deliberately disables implicit timer/score fallback. Its timer therefore remains unknown. Training-frozen timer crop [925,27,1000,67] permits a distinct explicit timer-only reader without changing identity references or numeric score policy.

Hypothesis/Change: candidate15 adds only the explicit timer reader. Its fixed sampled blind review finds23 correct,5 unknown,2 wrong; reject15 before full. Add an optional portable digits/fields `minimum_confidence` safety gate with fail-closed invalid configuration, retaining omitted-key behavior. Candidate16 uses0.90, the existing shared-timer fact requirement; no geometry/NCC/identity/spectator threshold is loosened. Training and original64-frame holdout remain separate. No Windows/Pi recognition branch.

Tests/Before/After: candidate16 independent holdout48 correct16 unknown0 wrong; fixed sampled23 correct7 unknown0 wrong; targeted timer field failures13→4 while score failures and frame-level FAIL remain unchanged. Ruff/mypy PASS; all regression1109 PASS6 SKIP in1344s. One standard full completes15149.129s with23 PASS55 FAIL4 NE, same assertion statuses as13, negative failures0 anddiscontinuity0.3411 timer values are accepted. Common4634PTS retain identical non-timer observations excluding index renumbering; adaptive sampling adds27PTS, removes0. No genuine round-start/end or visual/map event improvement is established.

Conclusion: reject16, not adopted. Actual full frames show1:26→4:26 atPTS124.486003/confidence0.93834,1:15→4:15 at135.802669/0.95371,0:55→10:55 at156.002669/0.92050. High OCR confidence and sparse holdout success do not establish full safety. These post-prediction error reviews are diagnostic evidence, not training or independent full ground truth. Do not increase the threshold to fit these errors, infer expected timer values from temporal sequence, or claim remaining3411 values correct. E2E infrastructure remains useful; timer OCR profile remains unqualified. Evidence: e2e_reports/match_001/profile16_diagnostic_assessment.json and local outputs/recognition-investigation/timer-only-profile15/full16. Geometry, identity, round-boundary and score shortcomings remain open; Windows runtime unverified.

## Candidate17: fixed white OCR rejected by sampled pixel review (2026-10-08)

Problem/Evidence: candidate16 full accepts1:26→4:26,1:15→4:15,0:55→10:55 aboveconfidence0.90. Hypothesis: background contributes misleading bright strokes; existing digits OCR `white_text_threshold: 200` could remove contamination. This fixed threshold comes from previous numeric preprocessing, not a sweep on errors/holdout.

Change/Tests: no production code change. Clone16 to local17 and enable existing fixed200 white OCR, retaining0.90 confidence, complete identity/mask assets and disabled score fallback. Previously blind-labeled64 even training gives56 correct8 unknown0 wrong (raw44 correct20 unknown after identical timer format gate). Freeze profilefingerprint621dfa6941e3111749ec415b499769f4e12a3480c0622d693f66d29b038322c2 before new64 odd-holdout pixel labels/predictions. These holdout images give53 correct11 unknown0 wrong. Three known16 errors become2 correct1 unknown; these already inspected errors are diagnostic controls, not independent qualification.

E2E before/after: native targeted13 frames149.921s gives1 PASS12 FAIL0 NE; native fixed sampled30 frames325.078s gives8 PASS11 FAIL11 NE (baseline7/12/11). Terminal verified sampled pixel review is27 correct2 unknown1 wrong: PTS124.536003,actual1:26→4:26 atconfidence0.93759. States, flags, ownership and all non-timer values equal sampled13. Conclusion: reject17 before full despite aggregate PASS gain and independent holdout success; profile not adopted. No further full run or confidence retuning on this failure. Source changes/tests/full rerun are not applicable to this local configuration diagnosis; future recognizer changes require their own regression and real-video qualification. Evidence remains local at outputs/recognition-investigation/timer-white-ocr-training.


### 2026-10-08: Round lifecycle prerequisite audit after failure classification

- Problem: round/package scope affects 33 FAILs; no new numeric candidate is justified.
- Evidence: current-main safe profile13 replay of six saved real frames is unknown with HUD confidence 0; R1 start lacks Ability/Weapon identity, R2 start lacks Weapon identity. Purchase banners visible in two images have shared_banner=false, while two combat/death backgrounds have texture shared_banner=true. Saved full16 boundary ranges contain 32 unknown observations, no semantic phase flags or known score pairs, even where numeric timer resets exist.
- Hypothesis: timer-only improvements cannot establish round lifecycle; source-qualified phase/score and independent identity are prerequisites.
- Change: read-only saved-frame diagnostics plus `docs/round_lifecycle_prerequisite_audit.md`; no production/profile/GT/threshold changes.
- Tests: existing native diagnostic hook completed six isolated queries with three genuine calibration frames each. No claim about continuity/events from sparse input.
- E2E before / after: unchanged 23 PASS / 55 FAIL / 4 NE; no additional full run.
- Conclusion: next work must qualify phase/score/identity inputs together before boundary integration. No new recognizer candidate, guaranteed PASS gain, or adopted timer profile.
