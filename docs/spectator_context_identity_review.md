# Spectator context and identity review

This review binds the diagnostic run at HEAD `c24ec31fc77cd0cdcdb53b192567455a5cf1c2e7` to the clean baseline analyzer `5b7a7e26c670cfc999839dcecd42c77065d19a24`, the fixed replay manifest `f8267c437f95cb534c06d80a459961409323688f9b7a76a728b719b0350e74f1` (1,026 frames), and HUD profile fingerprint `e7987bf758eb2dca8211149b6fde9bddcb04a07997f1fb66cb38e8c677580e57`. The profile fingerprint matched exactly. A read-only source-tree comparison found no production source changes between diagnostic HEAD `c24ec31fc77cd0cdcdb53b192567455a5cf1c2e7` and report-generation HEAD `523141e554ccbe08ae3483a52f7cb89c2c53b0ed`; the production-source working tree was clean. Feature-reader and template source hashes are recorded in the companion JSON.

## Full-context replay

The full-context replay reran the actual production template detector over the fixed replay with temporal features reconstructed from native presentation times. All 301 saved reasons matched the replayed production reasons. Among these 301 cases, production reasons were 25 `icon_absent`, 42 `icon_present`, 118 `icon_roi_obscured`, 114 `icon_roi_unobservable`, and 2 `icon_structure_ambiguous`.

The 118 obscured cases split by reconstructed context into 52 buy-grid-only, 20 buy-grid plus short-X, 45 no basic context plus short-X, and 1 abrupt-luminance-spike case. These overlapping context signals explain global detector veto inputs; they do not establish physical occlusion or spectator truth.

The ROI-only diagnostic on the separate 118-case saved-obscured subset returned 51 absent, 14 present, 52 unobservable, and 1 ambiguous. The full-context count of 114 unobservable is across all 301 replay cases. Those counts have different denominators and show why the local-only probe cannot stand in for production context. Keep the global-context guard in place.

## Locked appearance sample and crop audit

The 25-case appearance sample is stratified across abrupt-only (1), buy-only (8), buy-plus-X (8), and X-only (8) contexts. It comes from the same recording and is not prevalence sampled. Reviewers marked a Buy menu visible in 0/25 cases. The local close-anchor helper flagged 16/25; that is a diagnostic sample count, not a population false-positive rate. The appearance review was locked before joining the helper output, while the root review was informed by aggregate helper results and was not a blinded qualification.

A corrected native-aspect crop review covered all 25 cases across seven pages; reviewers found a recognizable Buy close button in 0/25. The frozen pixel ablation kept the patch definition fixed before measurement. The helper returned true on 16/25 original crops, 7/25 after complement mean-fill, and 3/25 after glyph-patch mean-fill. These artificial edits show sensitivity under the chosen ablation; they do not prove semantic causation.

## Decision and limits

**KEEP CURRENT safety behavior.** No production behavior, threshold, or eligibility change was made. The global-context veto remains active. This offline same-recording review makes no live behavior or oracle/ground-truth claim.

Unconfounded Hough attribution is complete; its results and limits are below. The companion JSON records hashes for the replay, appearance review, corrected crop receipt, and frozen ablation artifacts.


## Local observability and unconfounded segment evidence

The 114 saved local-unobservable cases first fail: std79, acutance20,
mean8, sharpness6, black clipping1. These explain the existing contract,
not physical spectator absence. The dedicated detector has no reference asset;
its75x83 ROI remains subject to both local prerequisites and the global veto.

An independent trace of the actual production Hough helper exactly reproduces
all34 crops:25 reviewed no-menu appearances,3 training close-X images and6
visible-X development images. No pixels are edited in this attribution. The
global two-sign predicate flags16/25 no-menu appearances and9/9 X controls.
Both sign families have midpoints inside the existing center patch on3/25
no-menu images and9/9 controls; outside that patch,13/25 and0/9 respectively.
Excluding upper-left patch segments at the list stage leaves5/25 no-menu
candidates and all9 controls. This supports spatially distributed scene/text-like
diagonals as a mechanism for broad helper responses. It neither identifies text
contents nor establishes a safe menu witness: center support still overlaps
three reviewed non-menu images. Training controls and previously inspected
development controls are not new holdout evidence.

**KEEP CURRENT** production safety behavior. The next experiment freezes this
descriptive center-support rule and evaluates32 newly selected unreviewed
actual-helper-positive fixed-canonical images. Selection uses native-order
quantiles and excludes available prior review manifests, never candidate scores
or GT. Blinded appearance review and explicit exclusion limitations precede
any qualification claim. No absence gate or blocker will be bypassed.

## Verification

Full pytest with the external pack:924 passed/2 existing optional-fixture skips
in274.53 seconds. Ruff src/tests/scripts and mypy src(86 files) pass.
Production remains unchanged; no new Clean E2E is run for these aggregate/docs
changes. The current clean baseline remains22 passed/56 failed/4 not evaluated,
with negative assertions20 passed/0 failed. Fixed replay manifests remain frozen.
