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


## Native-resolution world-chain hypothesis (2026-10-09)

The [latest-main R1 diagnostic](scene_world_resolution_investigation.md) tests original1920×1080grayscale while preserving normalized spatial limits, NCC0.90and the existing reviewed source footprints. Prefix support remains0/35; separate stable support changes4→0/29despite more initial features141→162. Removing downscaling alone is rejected as a remedy. Failure remains unknown rather than a cut label; production/qualification/events/82assertion rows are unchanged. Ten unit tests, Ruff and fresh mypy102files pass. Canonical Current/Delta remain unmeasured; no full E2E was run.


## Passive R1 world-chain rejection-stage follow-up

[Per-region evidence](scene_world_stage_investigation.md) identifies the missing source-world row: native upper regions lose all35tracks below unchanged OpenCV conditioning, while95original-world-supported points remain in one row. Canonical support loses its final upper witness as an affine outlier after earlier conditioning losses. A proposed lower ROI is rejected before matching because hands/charm and faint ability UI enter it. Instrumented results exactly match preserved behavior on128links;12tests/Ruff/mypy102files pass. Production, qualification, events and82assertion rows are unchanged. Canonical Current/Delta remain unmeasured; no full E2E was run. Next source work needs distinctive, reviewed world-only structure and pose coverage, rather than looser acceptance.


## Adjacent source-world photometry follow-up

[The declared alternative diagnostic](scene_adjacent_world_investigation.md) retains original world-feature identities and their seed NCC while measuring adjacent whole-crop appearance. Stable support3→5/29 confirms cumulative seed comparison explains two early abstentions, but the chain still stops at4.002669 before the timer transition: upper warped NCC0.833926, independent raw NCC0.896447, and the other upper crop's interior texture below1. Prefix remains0/35; no unknown is relabelled as a cut. Existing-mode dictionaries are unchanged on116links;15tests/Ruff/mypy102files pass. Production, qualification, events and82assertion rows are unchanged; canonical Current/Delta remain unmeasured. Strict full-footprint signal assessment is the next untested hypothesis, not a margin/threshold fallback.


## Complete source-footprint diagnostic follow-up

[The explicitly declared full-valid footprint](scene_full_footprint_investigation.md) excludes every sampled padding contribution while using complete reviewed crop support. Stable links5→11/29 reach the last purchase-phase image; all six photometric regions are strong there. At phase disappearance4.102669, all five remaining seed-region1tracks are original-seed partial-affine outliers, leaving only two seed regions, so no chain/event is bridged. Existing defaults are exact on174links;18tests/Ruff/mypy102files pass. Production, qualification and82assertion rows are unchanged; canonical Current/Delta are unmeasured. Next diagnose the source-camera projection residual, preserving the third-region requirement and HUD geometry policy.


## R1 camera-model membership follow-up

[The source-camera audit](scene_camera_model_investigation.md) finds that the original similarity RANSAC mask contains63/68points at phase disappearance, whereas the final same-matrix2pixel forward error includes66. An explicitly declared diagnostic keeps original consensus>=0.90and adds bidirectional final-model membership, original-seed/adjacent NCC>=0.90and distributed world-only crop photometry. Training support11→22/29now spans both2:25frames and the1:39transition; it stops at4.286003without reacquisition. Visible scene continuity is supported on these development frames; uninterrupted game time and independent qualification remain unproven. Existing defaults are exact on203links; exposed cut/duplicate controls reject,26unit tests/Ruff/mypy102files pass. Production and all82assertion rows are unchanged; canonical Current/Delta are unmeasured. No full E2E was run. Next freeze the method and qualify independent world-only scene/UI evidence before activation, preserving the separate R2/result gates.


## Frozen final-membership cohort result

[The pre-reserved camera cohort](scene_final_membership_cohort_investigation.md) yields0/33supported links on36native images, with0PNG-byte overlaps against2098previously stored images. The first wall seed retains94identities in6regions but fails unchanged0.90valid crop coverage; two other poses contain players/knife/UI in the fixed footprints and lack world-only seed attestation. Reviewed panels show continuous-looking motion rather than proving a cut. No qualification or runtime event follows; no code is tuned to this result.28tests/Ruff pass, production and82assertion rows remain unchanged, canonical Current/Delta are unmeasured. The next source contract must separate reviewed seed eligibility, current occlusion and motion-dependent appearance footprint; changing camera models or OCR thresholds does not resolve this blocker.


## Frame-bound world review eligibility contract

[The offline review gate](scene_world_review_contract.md) separates reviewed world-only seed/current footprints from matching scores. It pins canonical pixels/native PTS/video/epoch/provenance, rejects unreviewed or occluded footprints and terminates on missing review, gap, duplicate or cut without reacquisition. Three real seed examples change3hypothetical initializations→1reviewed; two unsafe/unattested seeds are rejected before extraction. The valid wall seed still abstains at the original coverage predicate, so no real support or boundary is invented.38related tests/Ruff/fresh mypy102files pass; production and82assertion statuses remain unchanged, canonical Current/Delta unmeasured. This wrapper is diagnostic only: offline annotations are not runtime truth or producer qualification. Next address projected-world appearance coverage and current occlusion without lowering0.90floors.


## Reviewed projected-world appearance development

[The declared projected-footprint diagnostic](scene_projected_world_investigation.md) reuses the exact existing adjacent source-camera transform on the exposed wall pair. Current bilinear taps must all lie in explicitly reviewed world; complete-source coverage>=0.90/NCC>=0.90are unchanged. Appearance support0→6regions, minimum NCC0.974528, explains fixed-crop coverage loss while94original identities remain. This is one-link development evidence; the original tracker still abstains and is not revived. Default decisions are exact on203links, exposed cut/duplicate controls reject,44tests/Ruff/fresh mypy102files pass. Production and82assertion rows remain unchanged; canonical Current/Delta unmeasured. Next integrate continuous source/current world eligibility and projected appearance before independent qualification, never copy offline per-frame annotations into runtime truth.


## Continuous reviewed projected-world checkpoint

[The integrated diagnostic](scene_projected_chain_implementation.md) preserves original world identities/current flow-footprint review while using projected appearance at unchanged0.90coverage/NCC floors. The exposed12native-frame wall episode changes0→4/11supported links; at2.586003hand/unknown lower-footprint review terminates tracking and no later image rejoins. An initially overlapping unknown annotation was correctly rejected; consistent positive-mask encoding leaves all first5rows unchanged. Existing defaults are exact on203links, exposed cut/duplicate controls reject,53tests/Ruff/fresh mypy102files pass. Production and82assertion rows are unchanged, canonical Current/Delta unmeasured. No qualification/event/full E2E is claimed. Next verify the actual R1transient episode, then independently qualify source/current semantic evidence before runtime activation.


## Actual R1 projected-world transient replay

[The frozen30-native-frame replay](r1_projected_chain_investigation.md) supports22/29links, unchanged count versus the previous final-membership diagnostic. Phase disappearance/both2:25frames/first1:39all have six distributed projected world regions with minimum NCC0.995367/0.995436/0.943096/0.952934. At4.286003the unchanged original model-consensus gate fails and tracking never rejoins. This directly reinforces visible scene continuity with transient UI, not uninterrupted hidden game time or runtime qualification. Shared replay CLI verifies code/source/PNG/pixels/coverage terminal bindings in9.819518seconds. Core bytes remain those with53tests/mypy102files passing; fresh Ruff passes. Production and82assertions remain unchanged, canonical Current/Delta unmeasured, no full E2E. Next implement image-derived world reference bootstrap/current occlusion with independent qualification; offline per-frame masks are not runtime truth.


## Image-only reviewed-landmark bootstrap result

[The strict diagnostic reference entrance](scene_world_bootstrap_contract.md) consumes current pixels without PTS/GT/per-frame world annotations. The unchanged unique reciprocal matcher supports only its own reference image, 1/7 exposed frames; all four actual R1 start-transition queries lack distributed quorum. This is rejected as a qualification remedy, not interpreted as a content cut. Matched patches do not authorize whole-ROI background masks. 62 related tests pass in14.84seconds, Ruff passes, and fresh mypy passes104source files on main80d0d46. Production and82assertion rows are unchanged; canonical Current/Delta remain unmeasured, with no full E2E. Next retain image-qualified source-world identities and reject current footprint occlusion without manual runtime masks before independent qualification; do not repeat reference-bank/threshold tuning.


## R1 tracked footprint scope audit

[The passive 15/21/31-pixel audit](scene_track_footprint_audit.md) finds complete projected original-source appearance support across the timer transient, but every critical all-size witness remains in one spatial row (0/6 distributed queries). Synthetic controls demonstrate both surrounding occlusion hidden by a matching central patch and small foreground hidden by mean NCC. These scores cannot authorize whole-ROI semantic masks or replace the missing distributed runtime producer. The unchanged diagnostic still supports22/29links; no production/qualification/event/canonical gain is claimed. All82assertions remain unchanged; canonical Current/Delta are unmeasured and no full E2E is run. Next source work must provide image-derived distributed background-domain evidence with explicit footprint/ambiguity/occlusion handling, preserving all floors.


## Distributed scene-domain ambiguity follow-up

[The frozen five-link domain audit](scene_domain_ambiguity_investigation.md) identifies distinctive upper-wall structure: domain0supports every transient link with NCC>=0.943096and no competing displacement in the declared17×17local lattice. Other high-NCC domains have5–39competing positions, so independently localized domain quorum remains0/5. Source-only tracking decisions stay22/29; no semantic mask, runtime proof, qualification, event or canonical improvement is claimed. Four focused tests pass; source/PNG/pixel/code bindings match terminal hashes. All82assertions are unchanged. Next test joint distributed camera hypotheses, preserving explicit competitors and complete footprints, rather than counting each repeated domain as independent evidence.


## Joint background-domain camera hypothesis checkpoint

[The complete local-lattice audit](scene_joint_domains_investigation.md) supports the fixed camera projection jointly on5/5critical native R1links with three-cell/two-row/two-column source/current witnesses and no surviving/unresolved local translation competitor. Per-domain independence remains0/5; it is not relabelled. Optional offset instrumentation preserves all five old domain dictionaries exactly; the tracker remains22/29. Eight new joint tests plus four domain tests pass, Ruff passes, and production/all82assertions are unchanged. This is exposed local appearance, not foreground-free semantic masks, hidden-time proof, qualification or canonical gain. Next freeze continuous source/limited witness scope and verify unexposed holdout/negative controls before runtime activation. No full E2E was run.


## Frozen joint source cohort: qualification withheld

[The36-frame native cohort](scene_joint_cohort_investigation.md) finds15previously exposed decoded images and no evaluated joint links. All three first-link original camera consensuses are below0.90(74.36%,84.21%,83.64%); the chain terminates without rejoining. Joint accuracy is not evaluated, rather than0/33wrong. Full-context review finds moving players/arms/knife/barrier/UI in fixed source footprints, so hypothetical seeds are not world-attested. No qualification/runtime event follows.15focused tests/Ruff pass; production and82assertions are unchanged, canonical Current/Delta unmeasured, no full E2E. Next complete image-only source-world seed eligibility before arbitrary-pose positive qualification; do not tune joint/consensus floors to this cohort.


## Stateless reference-domain initialization contract

[The image-only source initializer diagnostic](scene_domain_bootstrap_contract.md) explicitly distinguishes reviewed reference assets from previously observed native frames and rejects landmark-scope promotion/competing reference selection. Eight exposed images yield only the self-reference proposal; all actual R1transition queries fail unchanged global model consensus before joint appearance. The static route is rejected as a sufficient reacquisition/qualification remedy; no threshold/bank tuning follows.22related tests/Ruff pass; production and82assertions are unchanged, canonical Current/Delta unmeasured and no full E2E. Next preserve the measured continuous source-world chain from an actual image-supported seed, with explicit current/temporal scope and independent qualification; a reference asset cannot supply a prior native observation.


## Observed source seed to continuous image-derived scene links

[The complete observed-source diagnostic](observed_scene_chain_contract.md) binds the first actually observed native PTS/pixels without counting reference assets as a previous source frame. No manual current-frame masks are supplied. Original identities plus fixed joint appearance reproduce22/29native R1links including all5critical transient links; at4.286003original model consensus fails and the episode never rejoins. Four protocol and two image-only synthetic controls reject all links/rejoin.13related tests/Ruff pass; production and82assertions are unchanged, canonical Current/Delta unmeasured, no full E2E. This is exposed limited-scope appearance, not semantic foreground absence/hidden-time proof/runtime qualification. Next freeze independent continuous acquisition/holdout/negative assessment and source-confidence provenance before production integration.

## Native foreground change prevents a timer-only conclusion

[Native UI localization](native_ui_localization.md) measures29adjacent exposed R1
pairs and verifies saved PNG/pixel/source/profile/code bindings. At the first
transient frame, all six background NCCs exceed0.995, while non-UI whole-image
NCC is0.345489 and389,399non-UI pixels enter the descriptive change bin. Native
images show a different hand/knife presentation. Background scene appearance is
supported, but a normal view-model transition versus a scene-preserving content
jump remains unresolved. Do not promote earlier background-only support to a
pure timer/UI transition claim. No production contract, threshold, proof,
qualification or82assertion status changes;6diagnostic tests/Ruff pass and no
canonical E2E is run. Next establish independent foreground animation continuity
controls within this recording before paired scene/UI authorization.
