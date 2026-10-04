# HUD value-reader and downstream evidence review

## Reproducibility

This diagnostic follows analyzer `0972db4db955ba659bbcc9be3bdea9097c00ec76` and clean report commit `9d4309278e18a1af6a7827dbf70629f794d8f0cb`. Video SHA256 is `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Private HUD profile fingerprint is `2bdae7b5358f79ab8130e8c4a125ff3f5a6b83fe7ffe7b79c67bcf52d41c0383`; layout SHA256 is `a3678bcd9df35d0932ae0e69495eb5b87a3ab40e9c988560d502a9507d59eef1`. All glyph models, crops and per-frame visual annotations remain private. Glyph supervision describes rendered characters for value reading only; it cannot enter identity logic.

## Current blocker

The clean 4,081-observation run has 166 live observations but zero nonempty values in each of thirteen audited fields: HP, armor, current/reserve ammo, weapon text, timer, ally/enemy score, location, zone, kill-feed rows, ability slots and round-end text. The actual inherited profile contains an empty readers mapping, and build_readers builds zero readers. The default Tesseract executable is unavailable. This is an implementation/configuration gap, not evidence that all underlying glyphs are absent.

The runtime value reader is separate from HP/Ability/Weapon identity references. HudAnalyzer._read_values uses current calibrated crops; missing round_timer/ally_score/enemy_score readers fall back to the optional digit OCR adapter. Read values pass the existing fact confidence contract before normalization. Identity still requires HP + Ability + Weapon and checked Spectator exclusion at 0.90. Numeric recognition must not substitute for those gates.

## Diagnostic cohort and annotation quality

The preceding Report-only analyzer run supplies 4,009 native observations with zero missing frame joins. Forty-eight equal-duration blocks are assigned even=training / odd=holdout before examining pixels; nearest midpoint selects 24/24 frames. Exact full-image hashes do not overlap. Additional training samples, if required for sparse symbols, are nearest quarter/three-quarter positions within even blocks only. Frame times locate private diagnostic inputs; they are not reader features.

Independent image review found transcription errors and row shifts in the original private holdout annotations before reader evaluation. Those labels must be corrected against exact crop pixels, never against an inferred countdown. This audit prevents spurious recognition failures or successes. Whole timer strings are used only for diagnostic evaluation; model assets must be isolated individual glyphs with complete competitor alphabet coverage.

## Current segmentation and contract concerns

Full-ROI Otsu preprocessing merges the timer capsule/background into foreground in multiple original crops. Across the original 48, bright-polarity tall component counts are 1:12, 2:15, 3:17 and 4:4; dark-polarity counts are 1:12, 2:28 and 3:8. These counts are preprocessing observations, not recognition results. Any field crop or extractor revision must be learned from training pixels and frozen before holdout evaluation.

SegmentedDigitsReader currently filters small components before recognizing digits, then formats three/four digits by inserting a colon. Actual colon evidence and complete 0-9 template coverage are not mandatory in that path. A reader that ignores punctuation cannot safely establish timer format merely from digit count. Synthetic characterization and frozen glyph replay are required before activation; no production reader/profile is enabled in this diagnostic phase.

## Map configuration and ownership evidence

The exact recorded settings fingerprint `5fbf872a4d91c43787c91e3e33f0b58e133f06c65ae84672a41a42df763b8332` is reconstructed from HUD layout, HUD asset fingerprint and manual map ID only. It contains no optional visual-profile or map-client-build arguments. The runner includes those keys when their arguments are supplied, so this exact match confirms the current run omitted them. Bootstrapping the map ID and minimap ROI does not supply marker HSV definitions. Zero marker candidates therefore include a configuration gap; they do not establish an invisible marker.

Image-only affine/flow checks of six short sequences do not prove self-marker ownership. High-motion intervals contain effects, overlays or transparent world motion; the clean interval has weak camera rotation. Brightness sectors can reflect static map geometry. No production marker ownership or map-client validation is inferred from a north-up assumption or current state. Value reading is prioritized because clean glyph opportunities are already visible and it can advance facts without manufacturing map ownership.

## Decision and next experiment

NEED MORE EVIDENCE for numeric-reader activation. This is an active experimental state: expand training-only sparse glyph coverage, freeze complete-alphabet individual templates at score >=0.90 with competitor rejection, evaluate corrected block holdout, and test missing/extra colon and occluded glyphs. If existing segmentation fails, determine whether a training-derived field representation can separate characters and punctuation without whole-value templates or recording time rules. Production thresholds, identity contracts and optional-reader activation remain unchanged until evidence supports them.


## Frozen existing-reader replay

Training adds 48 even-block quarter samples to the original 24, with all odd holdout images unchanged. The training-only text field is normalized bounds [0.224, 0.211765, 0.776, 0.776471] within the configured timer ROI. Fifty-two of 72 training crops have exactly one polarity with the annotated digit count; twenty are excluded. Every digit has support from at least four distinct training blocks. This is count alignment, not proof that every segmented component is uncontaminated glyph ink.

At unchanged per-glyph 0.90 and distinct-class margin 0.04, frozen medoid templates produce full-ROI holdout 0 correct / 0 wrong / 24 unknown; the training-derived field produces 6 correct / 0 wrong / 18 unknown. Existing reader activation is rejected. The zero wrong results do not establish adequate coverage, nor do they solve punctuation observability.

The digit-zero training medoid has mean within-class pixel NCC approximately 0.415, while several other classes exceed 0.84. Background components, inverse-polarity holes and the normalizer's foreground-majority inversion are competing mechanisms to measure next; a low NCC is not automatically real font variation. The 24 evaluated holdout images become development evidence for any extractor revision. Fresh odd-block quarter images must be reserved before evaluating a revised candidate.

## Strict diagnostic format contract

A private binary-input prototype preserves score 0.90 and distinct-class gap 0.04, requires the complete ten-digit alphabet, exactly one two-dot separator between one/two minute digits and two second digits, valid seconds, no unexplained components and no foreground touching the crop boundary. Nineteen synthetic checks match expected outcomes. Padding-only crops remain accepted; actual edge-connected clipped ink rejects. The component ratios are provisional and require real training/profile validation. These synthetic outcomes do not establish real-video OCR accuracy or justify activation.

A shared reproducer is `python scripts/diagnose_timer_reader_contract.py AGGREGATE_OUTPUT`. It exercises actual SegmentedDigitsReader at 0.90 with complete synthetic glyph templates and no OCR fallback, then deletes its temporary assets. It records canonical, missing/duplicate separator, extra dot, partial alphabet and genuine boundary clipping cases, plus the reader source hash. It contains no recording-specific times, real crops, Agent knowledge or expected game states.

## Verification for this diagnostic checkpoint

pytest: 768 passed / 2 existing skips; Ruff src/tests/scripts: pass; mypy: 84 source files pass; diff check: pass. The two diagnostic tests verify actual-reader execution, aggregate output schema and genuine visible-ink clipping. Production source/profile activation is unchanged, so no new Clean E2E is required; latest committed-source E2E remains 22/56/4 with negative 20/0. This checkpoint immediately continues into extractor-mechanism diagnosis and fresh reserved-image evaluation.

## Continued diagnosis: normalization mechanism

The generic glyph normalizer infers polarity from foreground occupancy. Digit zero straddles its 50% rule: 20/34 training zero glyphs invert. Keeping an already known white-foreground mask increases mean zero within-class NCC from 0.311 to 0.892. Changing references alone while retaining query inversion is invalid; both query and reference normalization must use the same contract. The initial 24 holdout crops became development data after extractor inspection. Gaussian smoothing and three-level luminance clustering were development-only probes and are not enabled.

## Frozen strict v1 evidence

Seventy-two training samples come from 24 preassigned even blocks. Each selected digit reference recurs in at least three distinct training blocks, with per-class block support 15/13/8/5/6/9/5/4/4/3. Freeze the field and raw normal-polarity Otsu extraction before evaluating 48 reserved odd-block quarter samples. Their full-image and timer-ROI hashes overlap neither training nor the 24 development samples. Independent pixel transcription agrees for all 48. The frozen policy SHA256 is `1fa5f1809e181415f928de4f46f38f066b9680f6b37e5d0467248368e014c7c4`.

Reserved evaluation: 17 correct, 0 wrong, 31 unknown (19 glyph score, 11 boundary contact, 1 separator). This conservative coverage supports bounded optional value reading, not broad recognition accuracy. Eight malformed pixel mutations across 36 eligible source crops produce 0/288 accepts; twelve HP/ammo/score controls produce 0/12. Another 48 aspect-preserved non-timer crops from 48 source frames produce 0/48. Eight additional combat-report subwindows pass the frozen digit-and-separator geometry but all fail glyph scores: 0/8. The latter combined stress set is 56 crops from 53 source frames. Spectator game clocks are legitimate shared timer values and are not labeled negatives.

Actual production-class replay on all 4,081 saved native observations matches the frozen diagnostic exactly: zero value mismatches and zero confidence difference. It returns 1,587 values; this count is not an accuracy result. An additional 64 accepted crops, chosen across states and low confidence while excluding all 144 prior image hashes, were transcribed with predictions hidden: 64/64 agree. All evidence is from one recording; it does not demonstrate independence across episodes or other resolutions.

## Bounded production decision

ENABLE OPT-IN STRICT TIMER READER, followed by committed-source Clean E2E. The reader is restricted to round_timer, requires the exact ten-digit alphabet, fixed glyph score 0.90 and competing-class margin 0.04, observed two-dot separator, one/two minute digits plus two second digits, seconds below 60, and no extra or boundary-connected foreground. References are already normalized binary 32x24 masks. Confidence is the minimum accepted glyph NCC, not a probability. Current-frame pixels alone determine each result. Invalid explicitly configured strict profiles install a rejecting reader, preventing silent OCR fallback.

The training-derived field is a profile subregion, not a hardcoded production coordinate. Private activation profile fingerprint is `7c40cf8b719689173b9012ee33c4eb5bfda29619b8eb507e26bacfb68b712b27`; sidecar SHA256 is `e6b73b810f73dd2efbed44f4cbd240bc82214e634b4b4a545f082d8636285588`. All prior identity references and Report/Spectator contracts are inherited unchanged. Glyph assets and per-frame annotations remain private. The prior NEED MORE EVIDENCE decision above is historical; these new reserved and negative experiments resolve the bounded activation question.

Timer cannot satisfy missing HP/Ability/Weapon identity gates or unchecked Spectator exclusion. Shared timer values may survive non-live states; player-specific value clearing remains unchanged. A timer reset alone creates no round_start. Existing temporal logic also requires a buy/banner-to-live transition; round_end requires its banner plus corroborating evidence. No expected state or timestamp enters this reader.

Aggregate machine-readable evidence is in `docs/strict_timer_reader_metrics.json`. Reproduction requires the private frozen references and frame collection: validate policy/reference hashes, build the strict reader through HudTemplateProfile, and replay original timer ROIs using the frozen normalized subregion. Shared synthetic tests exercise format, competing alphabet, role, malformed assets and fail-closed OCR behavior without private assets.

## Strict reader integration verification

Full pytest: 775 passed / 2 existing environment skips (optional sibling validation pack and raw-video test input). Ruff src/tests/scripts passed; mypy passed for 85 source files; diff check passed. Production-class reserved replay is 48/48 identical to frozen predictions, with 17 correct / 0 wrong / 31 unknown; production malformed controls are 0/288 accepts and numeric non-timer controls 0/12. Private-profile activation is evaluated by a subsequent clean committed-source E2E; no results from that run are claimed here.
