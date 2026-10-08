# Round lifecycle qualification — work in progress

## Scope and provenance

The acceptance target is the complete source-frame → HUD evidence → lifecycle
decision → native event → RoundWindow → package association → trace → canonical
evaluator contract. Two trustworthy starts and one trustworthy end in the supplied
recording must be observed; passing synthetic tests alone does not complete it.

Work started from clean main `9bb50abd463ab0ef41fb35c59dbe0d7679a64082`, after
fetch and fast-forward pull, on `work/round-lifecycle-boundaries`.
The local safe baseline is `pi-structural-20261007-13`; the separate
`round-phase-text-20261008` profile remains an unadopted diagnostic candidate.
Private assets, recordings and raw outputs remain Git-ignored.

Input identity:

- Video SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.
- Pack fingerprint: `7f0b7798857670f08074adbeea73d24176967ad5bf1f2f7300d2c2f792cf956f`.
- Assertions SHA256: `c5e242b611ce227d1d2633e5e24c00dfe65168d8124ab58fbdea84b1d7f0d820`.
- Archived safe layout SHA256: `baa99f1c1f0b4b7b959ec80242a58996a85c6f018bbc0895b3ca728dcaa5f3f8`.

The latest shared report is historical: analyzer `e05c495`, dirty=true, executed
2026-10-07. Its 23 PASS / 55 FAIL / 4 NE must **not** be called a clean run of
the current branch. The imported safe full has 4,634 observations, one incomplete
package `[7.369336,171.002669]`, zero direct HUD events, zero direct Visual events
and zero start/end events. Transfer verification checked 225 file hashes and
three terminal input bindings for each imported run. No canonical full run of
this branch has yet been performed.

## Production call graph

`run_dataset_case.py` calls the shared real-video runner. `HudVideoProcessor`
extracts native-PTS Pass A, detects changes, extracts Pass B/micro candidates,
deduplicates frames and performs final `RealHudAnalyzer.observe_frames`.
The analyzer reads calibrated ROIs, source-supported semantic phase references
and numeric readers; it creates canonical observations and a separate evidence
map. `HudDirectEventBuilder` joins bounded HUD evidence and advances the existing
`RoundLifecycle`. Boundary actors remain `system`.

`RoundPackageBuilder` consumes those decisions, not evaluator timestamps. It
constructs observation/context windows, explicitly attaches the selected start
and end events, materializes snapshots and validates package schema v2.
`tests/e2e/trace_adapter.py` preserves package events and derives intervals from
raw observations with native window membership. The canonical evaluator then
compares that trace with the validation pack. GT is evaluation-only throughout.

## Confirmed association defects and fixes

1. Window construction deduplicated `(type, time)` using a set, but package event
   construction consumed the original list. A repeated boundary could therefore
   produce one window but two trace events. Both now consume one normalized
   population. The retained record is an existing decision, not a merged or
   higher-confidence invention. Conflicting continuity segments, including a
   missing segment versus a known segment, fail closed instead of last-write-win.
2. `DerivedEventBuilder` emitted a value snapshot for an all-missing value tuple
   solely because aggregate HUD confidence was high. It now requires at least
   one observed value. Zero is valid evidence; null and `unknown` are not.
   A missing-evidence interval resets the derived comparison history. Primary
   state/phase remain available through raw observations and trace intervals.
   This fixes the pre-existing preparation-context test without weakening it.
3. An incomplete fragment before an observation gap used the last qualified
   primary-state time as its endpoint, dropping later actually observed unknown
   frames and their independently accepted shared timer facts. Its endpoint now
   retains the last actual observation before the gap. The fragment still needs
   a qualified observation to exist, stays incomplete and never crosses the gap.

No actor, recognition threshold, identity requirement, sampler, schema,
validation pack, rule or evaluation policy was changed.

## Bounded native replay on Mac

The existing `scripts/diagnostics/diagnose_round_lifecycle.py` now also invokes
the native builder and exact trace adapter, reporting complete/incomplete
windows, evidence boundary times, observation/snapshot membership, unassigned
observations and trace boundary associations. It does not infer missing events
or invoke the evaluator on an incomplete cohort. Disconnected calibration-prefix
frames are not passed into package association.

Two diagnostic windows were replayed from the archived native frame population:
3.8–4.3 s (13 frames) and 111.25–111.6 s (6 frames). These are offline diagnostic
selection ranges, never production constants. All 22 distinct source images,
including three calibration-prefix frames, matched the saved Pi cohort hashes.
The original video and terminal raw hashes were checked before replay.

| Measured input/output on the same 19 frames | Safe profile13 | Unadopted phase profile | Delta |
| --- | ---: | ---: | ---: |
| Purchase template matches | 0 | 11 | +11 |
| Confirmed source-supported phase | 0 | 0 | 0 |
| Both scores accepted | 0 | 0 | 0 |
| Numeric timer accepted | 0 | 0 | 0 |
| Unknown primary state | 19 | 19 | 0 |
| Start / end events | 0 / 0 | 0 / 0 | 0 / 0 |
| Packages in these bounded windows | 0 | 0 | 0 |
| Unassigned observations | 19 | 19 | 0 |

The phase profile uses the legacy unmasked reference, not the newer structural
semantic-text candidate. Its nonmatch is unknown, not verified absence. The
comparison supports investigating the remaining numeric/global lifecycle input;
it does not support adoption or claim improved real-video boundary detection.
Private replay reports are under `outputs/round-lifecycle/`.

### Frozen structural semantic-text component replay

Additional source frames were obtained read-only from the Pi for the existing
frozen structural-text candidate. All three reference/mask/group asset hashes,
three training-frame hashes and all 21 independently reviewed holdout-frame
hashes were checked against their original records. The current production
`SemanticTextReference` was constructed with the frozen training crops and
threshold .90; no ROI, mask, reference or threshold was retuned.

Training support: 3/3. Holdout positives accepted: 8/8; positive unknown: 0.
Negative controls falsely accepted: 0/13; those 13 nonmatches remain unknown,
not verified absence. Lowest positive per-group NCC: 0.929437371011812.
Predictions disagreeing with the saved holdout record: 0/21.
These are replayed manual image-review cohorts, not new GT or a new independent
holdout qualification. They support integrating this frozen profile component
into a further bounded native replay, but do not qualify a lifecycle boundary.

## Qualification gates and remaining work

- Imported structural-text assets and exact current-production component scores
  now reproduce the frozen holdout. Full profile loading and native phase flags
  have also been replayed as recorded below; global lifecycle inputs still need
  qualification before profile adoption.
  A successful purchase match alone is not a start.
- The safe baseline has no accepted score/timer at the start windows; the
  historical timer-only candidate was rejected for confident wrong readings.
  It must not be adopted to force a reset or fill missing values.
- The existing start predicate also requires live first-person evidence. The
  global-round-evidence contract needs investigation separately from player
  ownership; no unknown frame has been upgraded to live in this work.
- R1 end images confirm the reviewed score/timer cut and a later TEAM ACE UI.
  The later banner cannot be joined backward across that cut. Independent
  pre-cut end/elimination evidence and source continuity protection still need
  qualification.
- The new package/trace diagnostic has synthetic two-round and unknown-only
  coverage. Full real-video start/end and correct R1/R2 package membership remain
  unproven. No negative-assertion improvement is claimed from an empty output.
- Next: frozen structural-text profile/native replay, independent numeric and
  continuity diagnostics, then qualified lifecycle inputs. Only after focused
  real-data qualification should the unchanged canonical full runner execute.

## Verification so far

Focused lifecycle, boundary, builder, event-source, shared-timer and trace tests:
**74 PASS**, including the explicit unknown-before-gap regression.
These include duplicate/out-of-order decisions, conflicting continuity,
two-round native-to-trace membership, unknown-only diagnostics and zero/missing
derived values. Existing tests were not removed or weakened.
Ruff (`src tests scripts/e2e` and the diagnostic): PASS.
mypy (`src/valorant_ai_coach`): PASS, 98 files. `git diff --check`: PASS.
An initial full regression (before the final missing-value fix) had 7 failures.
All seven were reproduced on an isolated archive of the start commit with the
same interpreter/dependencies (105 PASS / 7 FAIL / 1 SKIP for those files).
Two lifecycle-related failures now pass. The remaining four Spectator cases and
one macOS `/var`→`/private/var` path case are baseline failures outside the scoped
recognition changes. The fresh full regression finished with **1185 PASS /
5 FAIL / 5 SKIP** in 151.94 seconds. Its collected population predates the final
explicit unknown-before-gap test; that additional test passed in the 74-test
focused run. No all-tests-green claim is made. The optional real-video anchor
test and Windows/PowerShell checks were skipped; no skip is counted as PASS.
Windows runtime and exe packaging were not exercised or changed.

## Frozen profile integration and numeric-reader audit

`scripts/diagnostics/build_frozen_phase_profile.py` now bundles the existing
frozen semantic reference, mask, spatial groups and three training crops into
a portable, private diagnostic profile. It checks source/copy hashes, crop
bounds, threshold, complete asset resolution and source immutability before
publishing a new directory. Existing outputs cannot be overwritten. It does
not inspect holdout labels or change the default production profile. The base
layout is preserved byte-for-byte, including independent identity signals.

Generated profile fingerprint:
`8bb442b0ef90d87e9caed34133fdf18129078b0f4b6fa044ff6c6162993514c7`.
On the same 19 native images used above, this profile produces 12 purchase
template matches and 8 confirmed phase flags (6 in R1's window, 2 in R2's).
Primary state remains unknown on all 19; accepted score pairs and timers remain
zero. Boundary events and packages remain zero. This is improved phase evidence,
not completed lifecycle recognition or a new independent holdout qualification.

A separate imported, unadopted timer profile was replayed on the identical
population. Its timer reader is configured; both score readers are absent, and
OCR fallback is disabled. A transparent diagnostic wrapper records the original
reader result without changing input, return value, confidence or acceptance.
Of 19 timer attempts, 17 reject with `strict_timer_glyph_below_0_90`, one with
`strict_timer_foreground_touches_roi_border`, and one accepts `1:39` at
111.519336 s with confidence 0.9034993052482605. These times are diagnostic
measurements only, never recognition constants. Boundaries/packages remain zero.
The imported sidecar requests `comparison_preprocessing=gaussian3x3_v1`, which
the current strict timer loader does not implement. Thus this replay measures
current behavior, not parity with an unreviewed remote implementation. No
preprocessing variant or timer profile has been adopted.

The numeric audit makes two different blockers explicit: missing score-reader
configuration, versus configured timer-reader rejection. A zero accepted count
alone could not distinguish them. Detailed reader outputs stay under ignored
`outputs/round-lifecycle/`, never shared reports.

Latest targeted test invocation (`python -m pytest`, with ambient `PYTHONPATH`
unset): **103 PASS** across frozen-profile, boundary, event-source, builder,
shared-timer, lifecycle, semantic-text and round-analysis integration tests.
Profile regressions include changed assets/source hashes, invalid crop/threshold,
archive-root escape, overwrite refusal, portable assets and mid-build mutation.
The audited-reader test verifies unchanged result and rejection provenance.
Ruff: PASS. mypy: PASS (98 production files). `git diff --check`: PASS.
An initial console-script `pytest` invocation exposed a missing repository-root
import path in the new diagnostic test. The test now establishes that path,
matching existing script tests. Console-script recheck: **28 PASS** for the
profile/boundary files, with no test suppressed.

Next: inspect frozen timer training/holdout/control provenance and numeric
preprocessing mismatch, then qualify independent score and continuity evidence.
Canonical full E2E has not been rerun, and real start/end improvement remains
unproven.

### Fixed Gaussian timer representation diagnostic

Additional Pi records were retrieved read-only. Their hash chain is consistent:
training report → candidate freeze → fresh selection → reviewed labels → reader
predictions; all ten installed binary template hashes match the training report.
The saved same-video holdout reports 25 correct / 7 unknown / 0 wrong; eight
source-field type controls have zero false positives and four historical wrong
controls become unknown. Those controls are not independent natural timer-absent
full frames, and these saved Pi numbers are not Mac verification results.

An explicit `--timer-comparison gaussian3x3_v1` diagnostic mode now reproduces
the frozen representation hypothesis using the production strict reader's
unchanged segmentation, colon, border, format, NCC .90 and class-margin .04
gates. Only normalized glyph/reference comparison uses fixed Gaussian3x3
sigma0. It requires the same declaration in the frozen profile; it does not
modify the profile, its assets, the production reader or the default path.
Reports distinguish `production_reader_replay=false` from exact production
replay. Existing binary asset validation still executes before transformation.

On the identical 19 native images, timer acceptance is 17 rather than 1:
12/13 in the R1 window and 5/6 in R2. Remaining reasons are one glyph mismatch
and one foreground touching the ROI border. Values show source timer transition
from `0:00` to `1:39` / `1:40`; acceptance counts alone do not establish every
value's correctness or qualify a boundary. Unknown primary state remains 19,
score pairs remain zero, events/packages remain zero. This is a diagnostic
representation comparison, not production adoption or full-video improvement.

Latest full suite (collected before the optional comparison regression was
added): **1195 PASS / 5 FAIL / 5 SKIP**, 151.93 s. The same five independently
reproduced baseline failures remain. After adding the comparison, profile and
strict-timer regressions: **21 PASS**. Original assets, bounds, thresholds and
blank rejection are preserved; missing reader rejects instead of falling back.
Malformed missing/double colon, extra dot and slash controls remain unknown.
Diagnostic reports include an implementation SHA256 so a profile fingerprint
alone cannot misleadingly imply reader parity across comparison variants.
Ruff and production mypy pass; `git diff --check` passes.

Reproduction, from repository root with the imported private data present:

```sh
env -u PYTHONPATH .venv/bin/python -m scripts.diagnostics.build_frozen_phase_profile \
  --layout outputs/pi-import-20261008/outputs/hud_profiles/pi-structural-20261007-13/hud_layout.json \
  --reference-dir outputs/pi-import-20261008/outputs/recognition-investigation/phase-evidence/structural-text \
  --archive-root outputs/pi-import-20261008 \
  --output outputs/round-lifecycle/new-frozen-phase-profile

env -u PYTHONPATH .venv/bin/python scripts/diagnostics/diagnose_round_lifecycle.py \
  --video /Users/itoshinya/Desktop/Valorant_09-25-2026_0-37-29-379.mp4 \
  --source-sha256 71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06 \
  --raw-processing outputs/pi-import-20261008/outputs/recognition-investigation/timer-only-profile15/full16/raw_processing.json \
  --frames-root outputs/pi-import-20261008/outputs/recognition-investigation/timer-only-profile15/full16/processing_frames \
  --profile outputs/pi-import-20261008/outputs/hud_profiles/round-global-timer-glyph-20261008/hud_layout.json \
  --window 3.8 4.3 --window 111.25 111.6 \
  --timer-comparison gaussian3x3_v1 \
  --output outputs/round-lifecycle/new-gaussian-timer-diagnostic.json
```

These commands are private diagnostics, not the canonical evaluator. The new
profile output directory must not already exist. Omit `--timer-comparison` for
an exact current-production reader replay. No frozen frame times or reviewed
labels enter the runtime recognition logic.

## Score reader reproducibility and remaining lifecycle gate

The remote score candidate declares `strict_score_glyphs`, but the starting Mac
production factory has no such reader kind. These opt-in development sidecars
must not be mistaken for supported production configuration. They reuse binary
timer digit references; that reuse is a hypothesis requiring score-specific
qualification, not proof of matching typography.

`scripts/diagnostics/score_numeric.py` implements the frozen diagnostic hypothesis:
fixed white200 foreground extraction, one/two connected digit components,
consistent two-digit layout, no leading zero, all ten competing classes, fixed
Gaussian3x3 normalized comparison, NCC .90 and competitor margin .04. No
temporal prediction, expected score or label is input. A loader validates both
roles, exact preprocessing/threshold/margin declarations, bounds and reference
containment, and fingerprints the sidecar plus every used template. Production
factory/default configuration are unchanged; invalid declarations fail closed.

The native boundary-window diagnostic accepts an explicit `--score-candidate`.
This substitutes only diagnostic numeric readers, before the analyzer reads
real calibrated ROIs, and marks `production_reader_replay=false`. It never
injects a value, identity label or lifecycle decision. Base-profile and candidate
immutability are rechecked. On the same 19 start-window frames:

| Measured quantity | Timer-only diagnostic | Timer + score diagnostic |
| --- | ---: | ---: |
| Numeric timer accepted | 17 | 17 |
| Both score values accepted | 0 | 18 |
| Primary state unknown | 19 | 19 |
| Start/end events | 0/0 | 0/0 |
| Packages | 0 | 0 |

The score pair is 0–1 in the first window and 0–2 in the second; one second-window
enemy-score ROI rejects because foreground touches its border. This is source
display evidence, not an injected expected score or a definition of round ID.
The timer transitions are now observable, but the existing candidate and
confirmation predicates require `live_first_person` and aggregate HUD confidence.
Thus numeric recognition and global phase evidence alone do not yet yield an
event. Independent global-round confidence/continuity must be qualified without
weakening or changing player identity/ownership policy.

`scripts/diagnostics/replay_score_cohort.py` replays a frozen manifest by exact
encoded image SHA256 and native PTS binding. Its nominal field coordinates are
explicitly **not** a geometry calibration claim. The CLI verifies source video
SHA; it does not read reviewed labels or Validation Pack data. Post-prediction
offline comparison, outside the recognizer, reproduces the saved Pi holdout:
27 frames / 54 reads = **36 correct / 18 unknown / 0 wrong**. Predictions differ
from the saved record on **0/54** reads. All four saved evaluation input hashes
match the imported bytes. This is replay of an already reviewed same-video
holdout, not a newly independent holdout or a full native accuracy measurement.

Source-hash-bound spatial negatives were also replayed: **0 false accepts / 54
reads** (44 component-count rejections, 10 border rejections). These are two
background fields in three separately selected source windows, not natural
score-absent UI. That missing negative coverage, global continuity and end
evidence remain adoption blockers. No qualification file/profile was installed.

Current focused suite: **93 PASS** (profile, score diagnostic, strict timer,
boundary, builder, lifecycle, shared timer). Includes zero/two-digit grammar,
malformed leading-zero/three-digit/border/extra-component inputs, missing
alphabet, unchanged .90/.04, invalid declaration/path/bounds, asset fingerprints,
source-image mutation and mismatched PTS rejection. Synthetic score references
use the same white200 pipeline as score grammar tests, not timer Otsu references;
synthetic successes are not real-data qualification. Existing tests remain intact.
Ruff: PASS. mypy: PASS (98 production files). `git diff --check`: PASS.
Full regression remains the preceding 1195 PASS / 5 baseline FAIL / 5 SKIP;
it predates these diagnostic-only additions. No new canonical full E2E ran.

To reproduce the native numeric comparison, add the following to the preceding
timer replay command, using a new ignored output report path:

```sh
--score-candidate outputs/pi-import-20261008/outputs/hud_profiles/round-global-timer-glyph-20261008/score-reader-white-development.templates.json
```

To reproduce the frozen score field holdout, without loading its reviewed labels:

```sh
env -u PYTHONPATH .venv/bin/python -m scripts.diagnostics.replay_score_cohort \
  --video /Users/itoshinya/Desktop/Valorant_09-25-2026_0-37-29-379.mp4 \
  --layout outputs/pi-import-20261008/outputs/hud_profiles/round-global-timer-glyph-20261008/hud_layout.json \
  --candidate outputs/pi-import-20261008/outputs/hud_profiles/round-global-timer-glyph-20261008/score-reader-white-development.templates.json \
  --manifest outputs/pi-import-20261008/outputs/recognition-investigation/score-white-holdout-20261008/native-manifest.json \
  --frames-root outputs/pi-import-20261008/outputs/recognition-investigation/score-white-holdout-20261008 \
  --output outputs/round-lifecycle/new-score-holdout.json
```

## Source correspondence and shared score provenance

`scripts/diagnostics/measure_source_correspondence.py` measures camera-region
LK forward/backward tracks and nonflat 11px patch NCC using the frozen
`camera_lk_fb_ncc_diagnostic_v1` parameter declaration. The output explicitly
does **not** attest continuity, identify cuts, allocate segments or generate
events. Identical source/camera pixels are recorded separately, and remain
unqualified rather than being promoted as current evidence. Only two decoded
images are held in memory at once. Native archive/source hashes are verified;
explicit windows are offline selectors, not runtime timestamp constants.

On three archived windows (3.8–4.3, 74.3–74.6, 111.25–111.6), 21 adjacent pairs
were measured. The reviewed cut pair 74.402669→74.486003 still has 9 bidirectional
tracks and **3** patches with NCC≥.90, occupying grid cells [0,1,1,0,0,1,0,0,0].
Thus a few local correspondences, even over two rows/two columns, are not a
sufficient cut-negative control. R1 timer-reset pair has 7 such patches; the R2
reset pair has 7, all in one grid cell. These are descriptive measurements;
acceptance ratios or changed source populations do not prove continuity. The
imported composite v2 freeze explicitly says unqualified and records an earlier
stale-source-attestation failure. None of its assertions were installed.

`RealHudAnalyzer` now records `score_ally_value` / `score_enemy_value` in the
existing extensible ROI confidence map, parallel to `round_timer_value`. These
are only provenance for an accepted current-frame nonnegative integer reader
value with valid calibration. Missing/rejected/uncalibrated values get zero;
geometry feature confidence is not substituted. This is a provenance interface,
not recognition adoption or a qualified global-round confidence. It neither
changes player identity/ownership, aggregate HUD confidence, thresholds,
lifecycle predicates nor package generation.

The same 19-frame diagnostic replay confirms positive score-pair provenance on
18 frames; all 19 still have primary state unknown and aggregate HUD confidence
zero. Missing-value provenance is zero. Start/end events/packages remain zero.
Synthetic source-provenance regressions cover zero score, rejected/missing
readers, consecutive-frame reset, weaker cross-checked confidence and missing
calibration, while preserving unknown player identity and no boundary output.

Current targeted tests: **99 PASS**. Fresh full suite: **1225 PASS / 5 baseline
FAIL / 5 SKIP**, 150.97 s. The failure names are the same independently verified
macOS path and four Spectator cases; no existing assertion was weakened.
Ruff, production mypy (98 files), and `git diff --check`: PASS. Full canonical
real-video E2E remains unexecuted; this is not a completed lifecycle claim.

### Dense end-source follow-up

The original video was probed and decoded with the existing `VideoService` at
**every native presentation time** in the offline 74.3–74.65 s selector: 21 frames,
74.302669–74.636003. All returned PTS matched the requested native PTS, without
resizing, at JPEG quality100. Source SHA remains the recorded `71d585…36b06`.
These newly encoded frames differ from the archived JPEG population; no direct
accuracy delta between those populations is claimed.

Manual inspection of source images (not a runtime label) shows:

| Native PTS | Visible source UI | Encoded frame SHA256 |
| --- | --- | --- |
| 74.302669 | score0–1, timer0:29, a remaining ally portrait | `344310ad0cb1d7feeb09e8752658689c4cf7ccc04615ffbef12b075a22bf69cc` |
| 74.419336 | score0–1, timer0:29, report says round ongoing; no readable result text | `07aab45a24d5ad99c95231dfe2caefd755bf68a7552596a30e3ab7033995a4b6` |
| 74.436003 | readable TEAM ACE, score0–1, timer0:29 | `dfb2333953836463846ef0f496ba01cc5700f60c128fb51ca71dca7964222925` |
| 74.452669 | score0–1, timer0:06; result text not readable | `9027b3fa248f3a4d11ac00bf985222be46ed295d826fe60d0900a523bd07dc86` |
| 74.486003 | score0–2, timer0:06 | `6468918c2dd61f3090e4725772f2c761a80a8beed5155a91b1fd4424d2b5e524` |

The TEAM ACE frame lies **inside** the already reviewed cut uncertainty interval,
not demonstrably before it. It is not a qualified multi-frame pre-cut result
sequence. Its disappearance must not become runtime verified absence. The new
image narrows an end-banner candidate, but does not authorize joining the later
score update back across the cut. The source-pair 74.436003→74.452669 still has
83 descriptive high-NCC patches, further showing why correspondence count alone
cannot safely attest continuity in this edited sequence.

Nominal-coordinate frozen numeric diagnostic on these 21 images has 4 accepted
timers; image review shows timer updates before score updates. Reader rejection
does not mean timer absence. The sparse 74.402669→74.486003 pair concealed that
ordering. Neither diagnosis generated events or changed recognition defaults.

Next: qualify result-text/roster evidence as current independent observations,
including ambiguity/animation controls, without temporal joins across this
uncertain edge. Any later TEAM ACE banner remains prohibited from corroborating
an earlier end across an unqualified link. A single candidate image is not
production qualification; actual start/end/package completion remains unproven.

### Dense roster replay and phase-texture safety

`scripts/diagnostics/diagnose_roster_window.py` replays the same 21 dense native
PTS through `RealHudAnalyzer`, preceded by three genuine archived calibration
frames. It binds video/archive/profile/optional frozen numeric candidates and
frame hashes, validates observations, and does not accept expected counts or
states. The optional numeric comparisons remain diagnostic only.

All 21 ally counts are unknown; five enemy counts are accepted. The existing
roster reader divides each ROI into five equal strips and applies mean HSV and
contrast gates, then requires five known slots and temporal agreement. Colored
background can become an alive candidate after the visible ally portrait has
disappeared. Thus missing portraits and rejected slot readings are **not**
verified zero living players. No thresholds were relaxed and no elimination
evidence was generated. The diagnostic labels the legacy mixed ROI confidence
as `reported_roi_confidence`, not accepted-value provenance.

The same replay exposed a separate producer error: generic center-ROI texture
was emitted as `shared_banner` and combined with a score update to produce
`round_end_banner` at 74.486003, although no semantic result detector had matched.
`OpenCvHudFeatureReader` now emits this feature as `phase_banner_candidate` only.
Configured semantic phase detectors still promote their own independent result;
texture alone cannot prove a buy/result banner.

Before/after on **identical** 21 images: one unsupported end-banner flag removed,
accepted roster values unchanged, HUD events zero in both, primary unknown in
both. Reports are private `mac-dense-end-roster.json` and
`mac-dense-end-roster-texture-safe.json`. Three synthetic regressions cover
texture+score update, preserved configured semantic promotion, and native
no-boundary output; the related phase/temporal suite has **33 PASS**. This is a
false-evidence repair, not real-video lifecycle completion or an E2E PASS claim.

Fresh post-repair full suite: **1229 PASS / 5 baseline FAIL / 5 SKIP**, 155.99 s,
saved locally as `pytest-phase-texture-safety.xml`. The five failures remain the
same independently reproduced macOS path and Spectator tests listed above.
Ruff (`src`, `tests`, `scripts/diagnostics`, `scripts/e2e`), mypy (`src`, 98 files),
and `git diff --check` pass. The roster diagnostic regression explicitly covers
unknown versus zero, generic ROI confidence versus reader provenance, and
non-mutation of the source observation. No full canonical run was authorized by
these diagnostic candidates' qualification status: result/roster and continuity
remain unqualified, so real start/end/package completion remains unproven.

### Portrait placement diagnostic: fixed slots do not describe this roster

Source-image review shows five ally portraits in the initial calibration cohort,
but the remaining portrait at the end is right-aligned near the score. Equal
five-way subdivision of the configured broad roster ROI is not a stable mapping
of individual players. The ROI also includes scene/background pixels. A new
**diagnostic-only** `diagnose_roster_portraits.py` tests shape correspondence,
without turning template nonmatches into deaths or missing slots into zero.

The frozen local v1 manifest uses five 36×40 gray portrait crops from the first
source frame and hashes of three initial source frames. Coordinates are training
data, not embedded runtime constants. Manifest/layout/source hashes are checked
before and after the replay; training/probe overlap, changed inputs, out-of-ROI
crops, nonflat-invalid references, and existing output targets fail closed.
Output contains hashes and descriptive NCC maxima/locations, not image paths,
OCR, expected counts, live classifications or boundary decisions.

On the already-reviewed 21-image dense end cohort, the first training portrait
at x447 matches at x711, y30 in the first six probes: NCC 0.9658–0.9682. Thus its
location differs by 264 px from the training position. Its later maxima are only
0.399–0.518; those measurements are **unknown**, not verified absence. Other
portrait-reference maxima in this cohort are 0.380–0.475. These are correspondence
observations on a development cohort, not new independent holdout accuracy.

Two of the five references also fail a .90 comparison at their fixed original
training location on one of the other training frames (0.875 and 0.850). Neither
threshold nor cropping was adjusted after observing these outputs. A single
static portrait reference is not yet qualified, and cannot provide a trustworthy
zero-player/elimination fact. No roster values or lifecycle policy were changed.

Private report: `mac-roster-portrait-location-v1.json`. Focused diagnostic tests:
**9 PASS** (eight new plus the prior roster formatter regression). They cover
location matching, flat/invalid input rejection, source integrity, split
separation, bounded crop validation, non-mutation and non-positive outputs.
Next useful candidate must account for compacted portrait placement and rendering
variation with training-only fitting, then use fresh independent positive and
natural-background controls. Existing gray match failures cannot be repaired by
lowering thresholds or declaring absent portraits dead.

### Training-edge candidate and fresh source cohorts

Full-ROI location search on the three initial training sources does not repair
v1's 0.875/0.850 support failures. Fixed Gaussian 3×3 preprocessing, tested on
training only, also does not repair them. Neither was adopted. The next frozen
diagnostic method, `roster_portrait_stable_edge_ncc_location_v2`, uses Canny
60/120 and retains reference edges within one pixel of an edge in **every**
training crop. A fixed 3×3 dilation retains contrast neighbourhoods. It fits no
probe images, uses no geometry anchor, and keeps original zero-mean NCC .90.
Minimum support is 128 mask pixels and gray std5. Constant/undefined searches
remain unknown. A reference failing .90 on any training source cannot probe.

All five v2 training references meet the original .90 criterion: minimum per-role
NCC 0.926, 0.929, 0.984, 0.972, 0.947, with mask populations 1119, 1007, 1151,
1088, 1223. The numerical masked NCC implementation is tested against direct
Pearson correlation. Training-only mask fitting is deterministic and leaves
source arrays unchanged.

After freezing this candidate, the unchanged source video was decoded at all
native PTS in offline selectors 73.8–74.1 / 74.7–75.0 (36 frames), and then
0.8–1.1 (18 frames). Source SHA remains `71d585…36b06`; returned PTS exactly
match requested PTS. Encoding is quality100, no resizing. These frames were not
used to fit v2; no direct accuracy delta with differently encoded archives is
claimed. The fixed layout's `center_crosshair_area` supplies a separate spatial
non-HUD search control. Runtime recognition never receives these selectors.

Results on the 36-frame end cohort: first portrait .90 matches 18/18 in the first
window, 0/18 in the second; the other four have no .90 matches. Spatial controls
have 0/180 .90 matches, maximum .519. Review of the four cohort endpoints shows
one ally portrait before the ending animation and none in the later animation;
that limited review is not annotation of every frame or verified runtime absence.

The 18-frame preparation cohort exposes a remaining positive miss: first portrait
0/18 at .90 (minimum .855), other four 18/18 each. Controls 0/90, maximum .569.
The predictor was not changed after these results. The single-reference edge
candidate therefore **does not qualify** complete roster counting or elimination,
even though it handles a relocated portrait. No nonmatch becomes death/zero and
no positive lifecycle behavior was installed. This narrows the next training
requirement to independent rendering variants, not lower confidence thresholds.

Private reports: `mac-roster-portrait-v2-fresh.json` and
`mac-roster-portrait-v2-preparation.json`. Follow-up report schema now also binds
the edge-matcher implementation hash, since driver hash alone cannot identify
changes in the helper. The first reports precede that added field; their archived
bytes were not rewritten. Focused portrait/roster tests: **14 PASS**. Ruff, source
mypy (98 files), diff check: PASS. No production source changed in this follow-up;
the previously reported full-suite result remains 1229 PASS / 5 baseline FAIL /
5 SKIP, not a fresh full run including the new diagnostic tests. Canonical full
E2E and real round boundary completion remain unproven.

### Independent rendering bank: presence correspondence recovered

V3 keeps v2's edge-mask construction and .90 NCC, but supports a bounded bank of
up to three independently trained variants per portrait. Each group needs at
least three distinct source images; groups must partition the declared training
sources without reuse, and all source/probe hashes stay disjoint. Unsupported
variants cannot contribute even when a probe perfectly matches their pixels.
The output retains the original best variant's NCC and index; it does not sum
confidence, infer death, assign a living-player count or install a profile.

An additional training-only source window 2.0–2.1 was decoded (six native frames).
The first, third and last frames, 2.002669 / 2.036003 / 2.086003, form the second
group. The five unchanged training crop bounds were not moved. Each additional
reference has three-frame support >=.9926; no prior missed probe was inserted
into training. The two-group manifest was frozen before new probe decoding.

Development regression on the previously seen 0.8–1.1 cohort now gives .90
matches for all five portraits on all 18 frames, whereas v2 missed the first
portrait on all 18. This is a same-population diagnostic delta, not new holdout
accuracy. Spatial controls have no .90 matches, maximum .600.

Fresh native-PTS selectors 1.4–1.7 and 73.5–73.8 yield 36 new probe images, with
exact source PTS preserved and the same source SHA/quality100/no-resize policy.
First window: every portrait has 18/18 .90 matches; per-role minimum NCC .990,
.984, .980, .987, .976. Second window: first portrait 18/18 matches, the other
four 0/18. The 180 spatial non-HUD comparisons have no .90 match, maximum .562.
These are predictor outputs; they are not exhaustive manually labeled accuracy,
and correlated frames from narrow windows do not establish general performance.

Private reports: `mac-roster-bank-v3-development.json` and
`mac-roster-bank-v3-unseen.json`. Code/manifest/matcher/mask/source hashes bind
each run. Focused tests **21 PASS**, covering numerical NCC, group partition,
unavailable-reference suppression, bank variant provenance, immutable inputs and
no liveness inference. Ruff/source mypy/diff check pass. No production source or
confidence policy changed; no canonical full E2E was executed.

This resolves the measured single-reference presence miss without lowering a
threshold. It does **not** resolve current-frame verified portrait absence,
empty-roster observability, content-cut attestation, or the independent global
round evidence gate. Those remain necessary before actual start/end and package
separation can be claimed. Next priority is the global phase/timer/score lifecycle
gate rather than repeatedly fitting portrait references: a presence-only bank
cannot manufacture the missing elimination proof.
