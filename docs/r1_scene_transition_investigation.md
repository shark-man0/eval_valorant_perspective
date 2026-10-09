# R1 timer transition: independent scene investigation

## Problem

R1 displays `0:00 → 2:25 → 1:39`. The existing composite continuity contract uses timer plausibility and immediate previous purchase-phase presence. It rejects two links as `timer_transition_inconsistent`, although the display itself is visible. This investigation asks whether the camera scene changes independently of those UI pixels. It does not adjust recognition thresholds or produce real-source round events.

Worktree base: `0a606a0a3edb19ba4cd10d8007c2d045c39b2006` on main. Source SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Authoritative measurements, hashes and per-link metrics: [machine-readable report](../e2e_reports/match_001/r1_independent_scene_diagnostics.json).

## Evidence

The existing native archive contains all 30 consecutive source frames from **3.9026692708333335–4.386002604166667**, 256 ticks apart at time base 1/15360 (60fps). Every adjacent link is measured; no skipping. The CLI verifies source video, report, PNG and decoded-pixel hashes, then verifies terminal file/code hashes. Timing/display annotations are joined after measurements and never enter the image function. They are historical reader outputs, not new qualification or GT.

| Native PTS (sec) | Observed display | Purchase phase | Sequence observation |
| --- | --- | --- | --- |
| 4.086002604 | 0:00 | Last confirmed | Preparation evidence |
| 4.102669271 | 0:00 | Absent | Phase disappears |
| 4.119335938 | 2:25 | Absent | First anomalous display |
| 4.136002604 | 2:25 | Absent | Second native frame |
| 4.152669271 | 1:39 | Absent | Subsequent stable display begins |

Phase disappears 16.667ms before the first `2:25`; `2:25` spans two native frames. First `1:39` is 66.667ms after the last confirmed phase. These describe source evidence, not acceptance windows or production constants.

## Competing hypotheses

1. Temporary UI display transition in the same camera scene.
2. Whole-scene/content replacement coinciding with timer changes.
3. Edit/time jump preserving the same camera view.
4. OCR error without an actual displayed change.

Distributed background evidence strongly supports hypothesis 1 over 2 at the critical links. Native source inspection confirms the displayed characters, so correcting OCR to another value is unjustified. Hypothesis 3 remains indistinguishable from scene continuity by image correspondence alone. Scene continuity is therefore a narrower finding than uninterrupted gameplay time.

## Independent image evidence

Six fixed 1920×1080 background boxes, selected outside timer, phase, minimap, top HUD, crosshair and weapon in the R1 view:

```
(500,160,640,350)    (520,360,850,520)    (30,520,500,740)
(1320,160,1700,350)  (1320,370,1700,530)  (520,550,800,760)
```

Images are area-resized to 640×360. Rounded crop bounds and their exact three-times source footprints are recorded in code. Each crop has its **own** corner detector, LK pyramid, Farneback flow and ORB descriptors: masking feature centres in a full-frame pyramid would allow excluded UI to influence results and is rejected. No ROI is added or threshold tuned after seeing R2.

Measurements include per-region NCC/variance/absolute change; forward/backward LK consistency ≤1px; local 15×15 tracked-patch NCC ≥0.90; combined partial-affine RANSAC at 2px; crop-local dense flow; and mutual ORB ratio matches at 0.75. These are diagnostic parameters, not a qualified production continuity policy. NCC and motion estimates share image pixels; they are not statistically independent trials.

| Current PTS | Minimum of 6 NCC | LK patch ≥0.90 tracks | Supported regions | Affine inliers | Median forward/backward error (640×360 pixels) | ORB mutual matches |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 4.102669 | 0.992932 | 142 | 6 | 142 | 0.003367 | 0 |
| 4.119336 | 0.995436 | 135 | 6 | 135 | 0.002400 | 2 |
| 4.136003 | 0.929184 | 127 | 6 | 127 | 0.013138 | 2 |
| 4.152669 | 0.946006 | 137 | 5 | 137 | 0.012572 | 1 |

The reset link has near-identity affine motion. The next two links show coherent slight scaling (~0.9934/0.9936) and translation (~2.39/2.12 horizontal thumbnail pixels). This supports a continuous moving camera rather than unrelated scene replacement. Dense flow in weakly textured wall regions is not decisive. ORB has too little support to provide robust corroboration; it is explicitly inconclusive.

All 29 links remain in the report. Later, from 4.302669 onward, raw NCC degrades while camera motion increases. Low raw NCC alone does not prove a cut. Those links need additional motion-compensated evidence and are not included in the strong critical-transition conclusion.

Controls using the same shared image function:

- Changing **every excluded pixel** in both critical source images leaves the entire metric dictionary identical. This tests exclusion, not natural holdout qualification.
- An actual different archived scene has NCC below 0.51 in all six regions and zero accepted LK patches/ORB matches.
- A previously reported R1-end discontinuity span has weak region NCC but **55 accepted LK patches in three regions**. Tracking alone can survive a cut; it cannot authorize continuity.
- An identical source image has very high NCC and plentiful tracks. Duplicate-image and content-time vetoes must remain separate. Similarity alone cannot certify source continuity.

## Continuity decision

**R1: scene continuity is strongly supported at phase loss and both abnormal timer links; a transient UI display transition is the supported explanation of the image change. Complete content/game-time continuity remains unproven.** No automatic runtime continuity proof, round start, or player fact follows from this diagnostic.

R2 uses the same frozen algorithm and crops on 30 consecutive native frames, **111.202669–111.686003**. The 111.302669 link loses nearly all distributed correspondence. Actual images show a purple full-view effect/occlusion; teammate cards also overlap a crop. Later phase loss and reset occur during weak texture, with zero accepted LK tracks at the reset. R1 background selection is not a universal background selector. Thus R2 is **inconclusive**, not declared a content cut merely because NCC falls, and not qualified continuous by high NCC in an occluded view. This directly limits transfer of the R1 method without occlusion-aware source evidence.

## Contract change

This is a contract redesign specification; production adoption is deliberately not enabled by descriptive diagnostics.

Separate three outputs:

1. **Scene evidence:** image-only status (`supported`, `inconclusive`, `contradicted`) with source pair, distributed region/feature support, motion residuals and occlusion validity. It consumes no timer/phase labels.
2. **Clock/display semantics:** preserve every actual display, confidence and PTS. A changed display with phase loss can open `pre_round → transient_ui_transition`; it is not silently removed, repaired, or treated as active-round time.
3. **Content continuity/authorization:** known content cuts, duplicate pixels, PTS discontinuity, occluded/insufficient evidence and missing qualification remain vetoes. A scene match must never override an explicit content discontinuity.

A future qualified lifecycle may leave `transient_ui_transition` only after independently qualified evidence establishes a coherent phase/clock transition and temporal corroboration. Retain at least the existing ≥0.05sec duration and multiple distinct source-frame requirements; use no special cases for `2:25`, `1:39`, their timestamps or round IDs. Multiple unexplained clock jumps keep the transition pending rather than converting it into an event. Candidate provenance begins at independently evidenced phase transition, not a GT boundary. Event timing needs an explicit source-derived contract, not arbitrary backdating.

Training/holdout and natural negative controls must qualify this separation before runtime activation. Scene-preserving edits and occlusions are required rejection controls. It must remain restricted to system lifecycle evidence: HP, weapon, shot, death and other player-owned facts still require qualified identity/ownership. Existing `CompositeSourceContinuity` remains fail-closed; no current threshold or discontinuity policy is changed.

## Tests

Verification: **95 related unit tests PASS (6.88sec), Ruff PASS, mypy PASS (101 production source files)**. No full regression or fresh canonical E2E result is claimed.

Added unit checks cover excluded-pixel invariance across every metric, unrelated/identical images, unsupported size/dtype, and missing/duplicate/backward native PTS. Actual-video controls supplement synthetic checks without being labelled independent event qualification. Shared CLI verifies video/report/source-image binding before and after execution. The diagnostic returns no authorization flag or round event.

Reproduce (private native archive required):

```bash
python3 scripts/diagnostics/scene_correspondence.py \
  --source-report outputs/recognition-investigation/native-global-preparation-complete-20261008/results.json \
  --frames-root outputs/recognition-investigation/native-global-preparation-complete-20261008/window-000 \
  --video ValorantData/videos/Valorant_09-25-2026_0-37-29-379.mp4 \
  --window-index 0 --output /tmp/r1-scene-new.json
```

Output paths cannot overwrite existing diagnostics. R2 uses `window-001` and `--window-index 1`. Both platforms use the same Python/OpenCV code; Windows execution and numerical tolerance remain unverified.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Image-only native adjacent links measured (R1) | 0 | 29 | +29 |
| Image-only native adjacent links measured (R2) | 0 | 29 | +29 |
| R1 timer-dependent inconsistency links in historical contract | 2 | 2 (unchanged) | 0 |
| New runtime-qualified continuity links | 0 | 0 | 0 |
| New round events generated by investigation | 0 | 0 | 0 |
| Canonical PASS | 23 | Not rerun | — |
| Canonical FAIL | 55 | Not rerun | — |
| Canonical NE | 4 | Not rerun | — |

Final shared R1 diagnostic wall time 10.974sec; R2 10.498sec, including archive/hash checks. There is no comparable previous run for runtime delta. Neither runtime is an E2E performance result. No assertion is newly declared PASS. Historical negative failures/discontinuity violations remain 0; this diagnostic does not establish fresh E2E safety. Production source is unchanged. No targeted/sampled/full E2E is run because no qualified production candidate exists yet.

## Remaining blocker

R1's immediate blocker is now explicit: timer anomaly is not supported as a whole-camera replacement, but the existing contract conflates scene continuity with clock plausibility. The next implementation target is a **qualified transient-UI evidence contract** with separate content-time vetoes and natural occlusion/scene-preserving-edit controls. Independent lifecycle holdout qualification remains missing; do not fabricate it from these correlated adjacent frames.

R2 cannot reuse R1's proof through its purple occlusion. TEAM ACE reference transfer at NCC0.388 remains a separate R1-end blocker; no reference threshold change is made here. Additional video is not made a prerequisite for this source investigation. The broad round lifecycle goal and conditional 30/49/3 milestone remain incomplete.

## Diagnostic temporal contract prototype (follow-up)

A shared Python diagnostic state machine now implements `phase_candidate → pre_round → transient_ui_transition`, with a raw display ledger. Its output is explicitly **not** a continuity proof, clock qualification, event, or player-owned fact. A stable display only gets a descriptive `display_stable` flag; clock semantics remain unqualified and round authorization is always false. Actual display jumps are retained rather than ignored, and returning phase jitter requires a new confirmation span. Explicit cuts, duplicate source pixels, nonmonotonic PTS and gaps clear context. Inconclusive scene evidence also clears pending context without declaring a content cut.

Eleven unit cases cover arbitrary timer strings (not R1/GT-specific values), stable display without authorization, exact display preservation, cuts, duplicates, gaps, camera uncertainty, phase jitter, missing display and absence of player/continuity output. Related106tests passed7.02sec before a state-label correction; the final11prototype tests passed0.37sec afterward. Ruff and production mypy101files pass. No production source, acceptance policy or event contract is changed by this diagnostic prototype.

A conservative **development-only** replay predicate requires all six crop NCC values ≥0.90, distributed accepted LK patches and ≥90% affine inliers. This predicate is not the prior contextual scientific scene judgment and is not a qualified runtime rule. Applying it unchanged to all58native links reveals an important failed hypothesis: requiring raw appearance agreement in every fixed crop at every frame cannot preserve a phase-confirmation span through camera motion. R1 has6`phase_candidate` and24`unobserved` outputs; R2 has2and28respectively. Neither enters a confirmed `pre_round` or transient state. R1's4.002669and4.036003links have5and4high-NCC crops, respectively, and otherwise strong tracked correspondence; requiring all six discards them and resets accumulated phase evidence. Final state labels correctly clear an unconfirmed phase when the banner is absent.

This result does **not** overturn the critical-link scientific evidence, nor justify reducing NCC0.90 or bypassing continuity. It rejects this all-crops-per-frame predicate as a sufficient automated source producer. The diagnostic prototype alone does not qualify a production UI-transition path; the next concrete source work is motion-compensated distributed correspondence and explicit crop-occlusion validity, tested against the saved cut/duplicate/occlusion controls. No automatic phase-gap bridge, scene-preserving-cut acceptance or event creation is enabled.

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Diagnostic temporal prototype unit cases | 0 | 11 PASS | +11 |
| Native observations replayed through prototype | 0 | 60 | +60 |
| New runtime-qualified evidence / boundaries | 0 | 0 | 0 |
| Production source changes in follow-up | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | Not rerun | — |

Source/report/code-bound output: [transient contract replay](../e2e_reports/match_001/transient_ui_contract_replay.json). Reproduce without touching runtime assets:

```bash
PYTHONPATH="$PWD:$PWD/src" python3 scripts/diagnostics/ui_transition_contract.py \
  --input e2e_reports/match_001/r1_independent_scene_diagnostics.json \
  --output /tmp/transient-ui-new.json
```

The tool verifies its input and code bytes are unchanged before writing. Input report SHA binds the earlier video/frame measurements. No new reader, template candidate, threshold tuning, GT annotation, full E2E or Git publication is performed.

## Crop-local motion compensation

The next diagnostic source step now applies the estimated distributed LK affine transform **inside each original background crop**. Warping the full frame would let excluded UI enter a transformed region, so it is not used. An independently warped crop-validity mask excludes interpolation outside the source crop plus an eight-pixel target border. Pearson NCC is reported only with at least32valid pixels and both valid-region standard deviations ≥1. The transform, valid fraction and per-region NCC remain descriptive; the mask checks crop validity, not semantic occlusion.

A seeded synthetic camera translation has low raw NCC and compensated NCC above0.99 in all six regions. Excluded-pixel invariance still holds for the new metrics. Actual R1/R2 measurements use the unchanged30-frame archives and hash checks; **every previous raw metric is exactly equal**. Original version1source was byte-restored in the private archive, with its original hash2d9b7ceb9a47227b183dabb05aace4838e0c8228c28a4e0d4fb51a8e58771648, so earlier source bindings are preserved. The current script/report has its own new fingerprint.

For the 4.302669 camera-motion link, only2raw crops reach0.90, while5compensated crops do (remaining crop ~0.899 stays below threshold). Region3 is often **unknown**, rather than zero, after valid-border exclusion leaves insufficient texture. The all-six-region temporal recipe therefore remains rejected. No threshold is reduced and no aggregate production decision is invented.

On the saved discontinuity control, compensated crop NCC is approximately0.232/−0.534/0.175/**0.915**/0.086/0.626. A single region still matches across that cut; both raw motion and compensated NCC need distributed evidence and content vetoes. Different actual scenes have no usable transform and all compensated regions stay unknown. R2's purple effect and teammate-card contamination remain unqualified; affine compensation does not make occluded crops independent world evidence.

| Diagnostic metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| R1 processed frames / links | 30 / 29 | 30 / 29 | 0 / 0 |
| R2 processed frames / links | 30 / 29 | 30 / 29 | 0 / 0 |
| NCC ≥0.90 crops at R1 4.302669 | 2 raw | 5 compensated | +3 (different metric) |
| R1 wall seconds | 10.974 | 11.581 | +0.607 (+5.53%) |
| R2 wall seconds | 10.498 | 10.772 | +0.274 (+2.61%) |
| New runtime-qualified continuity / round events | 0 / 0 | 0 / 0 | 0 / 0 |

Runtime variation is a short diagnostic comparison, not an E2E speed claim. Final verification after all changes: **107 related unit tests PASS (7.31sec), Ruff PASS, mypy101production files PASS**. Canonical23/55/4remains historical/current unmeasured; no full run is justified yet. New report: [motion compensation, controls and bindings](../e2e_reports/match_001/scene_motion_compensation_diagnostics.json). The next unresolved producer requirement is explicit semantic occlusion/background validity with independent holdout and natural negative controls. No new video is required merely to investigate these saved source frames.

## Production camera evidence: phase contamination removed

### Problem / Evidence

Inspecting the actual opt-in `CompositeSourceContinuity.camera_image` shows that its canonical crop `(128,72)–(576,288)` in640×360 includes the purchase/result banner. The former3×3camera NCC grid could therefore reuse phase pixels as camera evidence. This independence defect is distinct from the diagnostic six-crop method and from the R1clock-semantic problem.

### Change

The opt-in shared production producer now excludes canonical rectangle **(224,28)–(416,120)**, including a margin around the phase/result panel, from each camera cell's NCC. Excluded values are removed rather than zero-filled, avoiding false similarity from identical fill. Valid vectors are reshaped to2D before OpenCV matching. NCC0.90, variance floor1, minimum3witness cells spanning2rows/2columns, accepted timer-pair checks, physically consistent clock/reset predicates, duplicate pixels, gaps, geometry and explicit content-cut vetoes stay fixed.

Method becomes `camera_grid_timer_phase_v3_phase_excluded`; proof provenance includes the exclusion coordinates. The global recognizer fingerprint changes, so previous qualification reports fail code binding and must be regenerated from actual reviewed evidence. No real report/profile is installed and no global route is enabled by this change. Standard identity-owned evidence remains unchanged. This exclusion addresses the named phase/result panel only: teammate overlays, weapon foreground, occlusion and scene-preserving edits still require independent validation; this is not a universal background classifier.

### Tests / Actual-source comparison

Four added unit cases cover exact witness invariance when excluded UI changes at640×360and1920×1080, a shared phase panel over unrelated backgrounds, and retained rejection of timer anomalies/content jumps. The complete selected set is135PASS8.71sec, including28composite-source cases; Ruff passes and mypy101production source files passes. The test count increase from107to135expands selected scope; it is not28new repository tests.

Actual comparison reads all60hash-bound native frames and58adjacent links from the existing R1/R2archives. Both legacy HEAD camera method and the modified shared production method receive the same images. Video SHA, report, image/pixel hashes and current code fingerprint are verified terminally. No qualification, lifecycle proof, reader inference or canonical evaluation is manufactured.

| Camera diagnostic | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| R1 spatial quorum links /29 | 25 | 25 | 0 |
| R2 spatial quorum links /29 | 24 | 23 | −1 (−4.17%) |
| New qualified runtime boundaries | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | Not rerun | — |

At111.386002604sec, the R2camera quorum changes from3cells to2after excluding phase pixels. The earlier archive called this link `attested_composite_link`; the corrected camera method lacks the required quorum. That is an image-evidence safety correction, not proof that the source has a content cut. R1camera counts are unchanged, and its0:00→2:25→1:39timer-dependent breaks remain rejected. No R1start or additional PASS is claimed.

Comparison wall time12.508sec includes both methods, frame decoding and terminal hashes; no directly comparable previous wall time. [Actual source comparison and bindings](../e2e_reports/match_001/phase_excluded_camera_diagnostics.json).

### Remaining blocker

The independent-scene contract now removes a concrete phase-contamination source from production evidence. Native runtime acceptance still lacks independently qualified continuity through transient UI changes and R2occlusion, plus R1-end reference transfer. These previously inspected source archives are development/regression data, not newly independent holdout. Full E2E is not justified yet: no source-qualified three-boundary candidate exists. GT/assertions, full sampler, geometry and player safety policies remain unchanged. Windows is unverified; shared Python code and explicit OpenCV array shapes are retained.


### Withheld-source qualification result

The scene method was frozen before three new native intervals were decoded. Review of all90frames shows foreground contamination and substantial raw-NCC abstention: camera quorum23/87, all-six raw NCC0/87, distributed LK87/87. Universal fixed-ROI qualification is rejected; this does not overturn the earlier critical-link scene observation. No event, threshold change or canonical gain follows. See [qualification decision, limits and next requirements](scene_continuity_qualification.md).


### Cross-region motion corroboration

Leave-one-region-out prediction reinforces R1critical scene coherence and contradicts the surviving matches on the known discontinuity control. It does not certify world background or uninterrupted game time. [Metrics, tests and remaining producer gap](scene_continuity_qualification.md#out-of-region-motion-consensus-development-follow-up).


## Opt-in production transient contract follow-up

The shared lifecycle now implements the pending UI state downstream of **paired source qualification**, without adopting diagnostic metrics as runtime proof. Current PTS/pixel-bound positive UI transition, clock-independent distributed background proof and accepted original display provenance are required. It retains every transient display, confirms a later coherent clock under the existing temporal duration, and resets on cuts/gaps/duplicates/epoch changes/state conflict. Native/package/trace tests preserve system actor, preparation association and one start per round. External supplemental scene/UI proof is rejected by the analyzer.

The real source producer and paired reviewed qualification are still absent; consequently no real R1 start, R2 start, package split or canonical gain is claimed. Historical report fingerprints describe their archived code versions; the newly changed lifecycle fingerprint does not retroactively qualify those reports. The unchanged legacy timer-dependent proof cannot be substituted for a scene proof. See [current contract, verification and remaining producer gate](transient_ui_lifecycle_contract.md).

Current follow-up verification: **200 related unit tests PASS (24.97sec), Ruff PASS, mypy102source files PASS**. No fresh canonical E2E or real-source qualification is claimed.


### Reviewed-world feature development follow-up

Restricting background labels to actually linked reviewed reference features raises R1descriptive support21→26of29native links and establishes diagnostic pre_round→transient_ui_transition while retaining every display. Whole-crop matching and a three-reference bank had failed the existing preparation-duration gate. No qualification or runtime event follows from training data; R2remains unsupported and canonical Current/Delta unmeasured. The prototype also no longer counts an initially unattested image toward phase duration. All219related cases pass26.05sec, Ruff passes, and production fingerprint matches the earlier mypy102file check. A prospective same-video holdout is frozen before decode. [Evidence, alternative hypotheses, tests and next gate](scene_world_feature_development.md).

## Frozen scene-world reference holdout result

The subsequent [native holdout investigation](scene_world_feature_holdout.md) measured36previously reserved frames /30adjacent links. The frozen method supported0links, including no distributed adjacent support in nearby R1 camera poses. All36masked panels were reviewed. This rejects production qualification of the current reference bank; missing support remains unknown, not a content-cut label. The original R1 critical-link evidence still favours visible scene continuity with a transient UI display change, while uninterrupted game time remains unproven. No scene/UI qualification or runtime boundary was created, no canonical E2E was rerun, and the82assertion statuses remain unchanged. Reference coverage and trusted producer qualification precede production activation.

## Wider world-patch search: insufficient remedy

The [96-native-image comparison](scene_patch_search_investigation.md) tests whether crop-local search range alone caused the failed scene qualification. Unique reciprocal NCC≥0.90search across existing non-UI crops reduces R1support26→19/29; R2stays0/29and the30former-holdout links remain unsupported. Rejection-stage diagnostics expose repeated-wall ambiguity and missing appearance support. Wider search is rejected as a sufficient remedy; no threshold relaxation, cut inference, qualification or event follows. Production and the82assertion matrix are unchanged; canonical Current/Delta is unmeasured. Next work needs distinctive world-feature structure/reference coverage and independent qualification, not looser patch acceptance.

## Joint feature translation trial

The [four-pose constellation investigation](scene_constellation_investigation.md) retains ambiguous patch alternatives and rejects competing distributed motions. Real poses yield0accepted tracks: either the finite peak budget cannot assess all alternatives, or the changed pose supplies no coherent distributed translation. Static reference-only eligibility removes21/114patches but does not establish support. This implementation is rejected for qualification; neither all spatial methods nor visible scene continuity is disproved. Production and all82assertions are unchanged; no qualification/event/full run or canonical gain is claimed. Next work is distinguishable reviewed background structure and reference pose coverage, preserving the source/producer qualification gate.


## Continuous reviewed-world chain checkpoint

The [continuous tracking investigation](scene_world_chain_investigation.md) preserves reviewed source feature identities without reseeding. Prefix support is0/35; separate stable-input feature support4/29 stops despite86tracks because spatial witnesses occupy one row. Dense source-world crops support3/29; adding a manually reviewed seventh background region leaves3/29 unchanged. Upper and added lower crop NCC values are below0.90 despite full valid warp coverage. These methods remain diagnostic-only and unqualified; missing support is not a cut label. Seven focused tests and Ruff pass. Production fingerprints and all82assertion rows are unchanged; no fresh canonical run, qualification or real boundary is claimed. Work pauses at the requested checkpoint with trusted scene/UI producer qualification still unfinished.
