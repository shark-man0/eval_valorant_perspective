# R1 joint background-domain camera hypotheses

## Problem

`GT-R1-ROUND-START` lacks a qualified scene/UI source producer. Individually localized background-domain support was0/5critical native links despite strong original-projection NCC. Evaluate whether ambiguous domains jointly support the existing measured camera motion, without moving the transform to make results pass.

## Evidence

Main `80d0d460b8e3a76d3c181e035c72cd10026f4252`. Thirty exposed native images, original PNG/pixels, source video and code were bound before/after measurement. This is development on one recording, not independent holdout. All five previous domain result dictionaries reproduce exactly after adding optional offset observability; unchanged tracker support remains22/29. The diagnostic takes current/prior pixels, declared source domains and the exact existing partial-affine transform. It receives no timer, phase, GT, expected event or current semantic annotation.

## Competing hypotheses

Per-domain ambiguity may persist as a common camera-motion alternative. Alternatively, distinctive upper-world structure may contradict translations that individually fit repeated lower textures. A missing/invalid candidate is not a contradiction; it must remain unresolved unless another observed domain positively contradicts it. This finite lattice cannot assess alternative affine/rotation/scale models or remote displacement.

## Independent image evidence

| PTS | Fixed-projection witness regions | Source/current spatial quorum | Joint competing offsets | Unresolved offsets | Local joint appearance |
| --- | --- | --- | ---: | ---: | --- |
| 4.102669 | [0, 2, 3, 4, 5] | True | 0 | 0 | True |
| 4.119336 | [0, 1, 2, 3, 4, 5] | True | 0 | 0 | True |
| 4.136003 | [0, 1, 2, 3, 4, 5] | True | 0 | 0 | True |
| 4.152669 | [0, 1, 2, 3, 4, 5] | True | 0 | 0 | True |
| 4.169336 | [0, 1, 2, 3, 4, 5] | True | 0 | 0 | True |

The actual phase disappearance, both2:25images, first1:39and its following image all have distributed complete-domain appearance at the fixed transform. At phase disappearance domain1is withheld because its projection touches protected pixels; its population is not trimmed or reported as observed. Five other complete domains supply the unchanged minimum spatial quorum. Later images support all six domains. Distinctive domains veto every assessed far translation that might individually fit lower repeated textures. Individual matches remain ambiguous; they are not relabelled as independently unique.

## Continuity decision

This strengthens visible-scene/UI-transition evidence on exposed training images. It establishes only joint appearance uniqueness within a17×17integer translation lattice around the fixed affine transform. It does not prove uninterrupted hidden game time, whole-ROI absence of foreground, all camera-model uniqueness, temporal qualification or a round start. Production continuity remains fail-closed and unchanged.

## Contract change

`domain_displacement_audit` optionally exports all289measurements per region without changing original outputs. `joint_domain_audit` rejects omitted/duplicate offsets and nonfinite scores, preserves unavailable texture/invalid projections as unknown, and requires at least three cells across two rows and columns in both source and current coordinates. Every fixed-projection witness must also fit a competing offset for that offset to survive; one known NCC<0.90contradiction vetoes it. If no contradiction exists but required support is unknown, the alternative remains unresolved. Offsets within the existing2pixel same-peak neighborhood are not distinct hypotheses. No alternative is chosen to repair the original camera model. Output explicitly authorizes no world mask or runtime proof.

## Tests

12focused cases pass in2.58seconds (eight joint cases plus four unchanged domain cases): distributed support, one-row rejection, common competing motion, invalid/texture-unknown alternatives, joint disambiguation, complete-lattice enforcement, and exact passive-sink equivalence. Five real prior-domain dictionaries also compare equal. Ruff passes `src tests scripts/e2e` and both diagnostics. Production is unchanged, so the preceding successful mypy104file check remains applicable.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Same-input unchanged tracker supported links | 22/29 | 22/29 | 0 |
| Per-domain independent localization quorum | 0/5 | 0/5 | 0 |
| Joint fixed-projection local appearance quorum | Not measured | 5/5 | Not comparable |
| Runtime scene/UI qualification | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | Historical23/55/4 | Not rerun | Unmeasured |
| Canonical negative / discontinuity violations | Historical0/0 | Not rerun | Unmeasured |

The30-image replay plus five complete-lattice joint audits took 13.067983seconds. Added instrumentation prevents a meaningful speed comparison with the prior domain-only measurement.

## Remaining blocker

The local joint contract now has positive source-image development evidence, but source-world bootstrap, current occlusion eligibility, full camera-hypothesis scope and independent scene/UI qualification remain unresolved. Freeze this method and test unexposed continuous native sequences and negative controls before attempting production activation. An image-only initialization must bind reference/profile/source evidence; no per-frame timestamp/hash annotation lookup may provide runtime truth. Mean NCC can hide small foreground, so local appearance must not be advertised as a semantic world mask. The next implementation should preserve source-world identities and carry explicit limited witness scope into continuous evidence. No OCR/geometry/safety threshold changes, GT injection, events or full E2E were made. R1remains first priority; R2/result are separate gates. Windows execution is unverified.
