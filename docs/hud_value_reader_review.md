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
