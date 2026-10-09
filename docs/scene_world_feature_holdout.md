# R1 scene continuity: frozen reference holdout

## Problem

R1's actual `0:00 → 2:25 → 1:39` displays must be distinguished from a whole-camera cut without reading timer/phase pixels in scene measurements. Distributed image evidence supports visible scene continuity at those links. The separate question here is whether the proposed world-reference method qualifies beyond its development poses. It does not.

Base main commit: `0a606a0a3edb19ba4cd10d8007c2d045c39b2006`. The source video SHA256 is `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.

## Evidence

The frozen four-reference method was measured once on six pre-reserved native intervals: 3.80–3.90, 4.39–4.50, 31.00–31.10, 0.60–0.70, 100.00–100.10 and 150.00–150.10 seconds. These are diagnostic input ranges, never production event times. All36native frames /30adjacent links were processed, with verified60fps coverage and256PTS ticks per adjacent frame. No skipping or input alteration occurred.

The36PNG hashes are unique and disjoint from152known development/control images. Training reference hashes are frozen. Source, reference assets, measurements and method bytes are checked before and after execution. The reservation's direct code map is empty due to a path-filter defect in its writer. Its candidate-report SHA nevertheless binds five explicit method hashes, which the runner resolves and verifies **before decoding**. The original reservation is preserved; the empty map does not allow arbitrary method changes.

Authoritative artifacts: [raw measurements](../e2e_reports/match_001/scene_world_feature_holdout_diagnostics.json), [post-measurement review](../e2e_reports/match_001/scene_world_feature_holdout_review.json), [reservation](../e2e_reports/match_001/scene_world_feature_holdout_reservation.json). Raw generation status remains `unreviewed`; the separate hash-bound ledger records subsequent inspection of all36masked source panels.

## Competing hypotheses

1. The reference bank supports ordinary continuous world motion across nearby poses.
2. It supports only a narrow set of reviewed poses because crop-local search cannot follow large displacement or occlusion.
3. Unsupported links are actual content cuts.

The result rejects hypothesis1 as a general qualification claim and supports hypothesis2 as a limitation. It does not establish hypothesis3: missing matches are evidence insufficiency, not a cut label. Scene-preserving temporal edits remain an independent unresolved hypothesis.

## Independent image evidence

The frozen matcher uses only crop-local reference/current background pixels: patch NCC≥0.90, forward/backward error≤1px, partial-affine RANSAC at2px and≥90%model inliers. A shared reference must contribute world-feature identities in at least three reviewed regions and source witness cells spanning two rows/two columns at **both** endpoints. Whole crops do not inherit a universal background label.

All six windows have **0/5supported links**. At3.80–3.90, early images have no reference matches, while later images regain up to102accepted tracks in a frame. This still provides no qualified distributed adjacent link. The wall/crack remains visible but changes pose and may move into excluded/occluded regions. At4.39–4.50, early frames have9–18tracks depending on reference, confined to one reviewed region; later frames have none. Camera motion, arms/knife and a character entering the view limit support. Neither result proves a cut.

The other four windows show different views or foreground/overlay interference; no reference tracks are accepted. Manual review masks timer/top-band and phase/result pixels. These are limited same-video image observations, not independent ground truth for uninterrupted game time or player identity. Zero accepted links means no accepted false-positive link was observed; it does **not** mean100%accuracy or successful positive qualification.

## Continuity decision

At the original R1 abnormal display links, the evidence still favours **a transient UI change within a visibly continuous camera scene**, over whole-scene replacement. At phase disappearance, all six regional NCCs are≥0.992932 with142consistent tracks. At the first2:25, minimum regional NCC is0.995436 with135tracks across six regions; reviewed-reference support also finds72or88shared world features. At the first1:39, five regions provide137tracks and reference16provides90shared world features. These measures share image data and are not statistically independent trials; distributed spatial and motion consistency supplies corroboration. ORB is sparse and inconclusive.

The holdout result prevents deploying that conclusion as a generally qualified runtime continuity token. Unsupported links remain unknown. Explicit content-cut, duplicate-pixel and PTS-discontinuity vetoes remain fail-closed. Image correspondence cannot by itself rule out an edit preserving the same scene.

R2 transfer remains unsupported under the frozen R1 method. No R2 threshold tuning or R1-end TEAM ACE reference relaxation was performed.

## Contract change

The implemented opt-in lifecycle contract separates qualified scene-only evidence from clock/display semantics. A paired qualification can use `pre_round → transient_ui_transition → round_active`, preserving every original display and resetting clock corroboration on each change. It never special-cases2:25,1:39, a GT timestamp or a round ID. Missing image support cannot supply preparation duration, including the initial frame.

Qualification and trusted producer integration remain mandatory. No actual scene/UI qualification is installed; the real analyzer has no qualified scene-only/positive UI-transition producer for this route. The failed positive holdout prevents enabling it. External `global_*` tokens cannot authorize events. Player-owned facts retain identity/ownership requirements.

This follow-up changes diagnostic execution and documentation only. Existing NCC, geometry, OCR, ownership, discontinuity safeguards, validation pack, assertion semantics and full sampler remain fixed. A reviewed reference profile is a future design requirement, not an adopted asset or a substitute for qualification. If these36frames inform redesign, they become development data and must never be reused as its independent qualification holdout.

## Tests

The native diagnostic completed with exit0 in41.614sec, once, using a blocking completion wait. Terminal binding and native-coverage checks passed. It generated no lifecycle event, qualification or canonical E2E result. The previous source-contract verification covered219related unit tests and mypy102production files; final current-worktree checks are recorded separately in [verification](../e2e_reports/match_001/scene_world_feature_holdout_verification.json).

No sampled/full E2E was run: there is no qualified production candidate to evaluate. No new canonical negative/discontinuity regression claim is made.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| R1 development descriptive links | 26/29 | 26/29 unchanged method | 0 |
| Reserved holdout frames measured | 0 | 36 | +36 |
| Holdout adjacent links measured | 0 | 30 | +30 |
| Holdout accepted links | Not measured | 0/30 | Not comparable |
| New runtime qualification / boundaries | 0/0 | 0/0 | 0/0 |
| Canonical PASS / FAIL / NE | Historical23/55/4 | Not rerun | Unmeasured |

Development26/29and holdout0/30use different inputs. Their subtraction is not an accuracy delta. The41.614sec diagnostic is not targeted, sampled or full E2E runtime.

## Remaining blocker

The current reference bank lacks positive holdout qualification and broad world-feature support across ordinary camera poses. The next implementation should address image-derived reference coverage and trusted scene/UI producers in the common Python/profile format, with newly separated holdout and negative controls. It must not bypass source-content vetoes or use timer values to select continuity references.

R1 end/result-banner qualification remains a separate blocker. Package splitting and canonical PASS gains remain unproven. No round start/end is generated from this investigation and no package-scope FAIL is declared solved.
