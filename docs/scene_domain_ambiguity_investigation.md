# R1 distributed domain displacement ambiguity

## Problem

`GT-R1-ROUND-START` still lacks a qualified independent scene/UI producer. Tracked points occupy one row. This shadow audit asks whether full background domains in other rows are both appearance-supported and distinctive, without manual current world labels or changing the measured camera transform.

## Evidence

Main `80d0d460b8e3a76d3c181e035c72cd10026f4252`. Thirty exposed native R1 frames are verified by original PNG/pixel/source/code pre/terminal hashes. The unchanged tracker supports22/29links. Five explicit native links are measured with its exact adjacent partial-affine transform; PTS is report metadata only. No timer/phase/Validation Pack/current semantic mask is supplied.

## Competing hypotheses

The missing upper row might have no distinctive image evidence, or local point conditioning might discard distinctive larger structures. Strong NCC alone may also describe repeated structures at competing positions. This frozen diagnostic assesses all289integer translations in a17×17lattice around the original projection. It does not optimize or replace the transform. The existing0.90appearance floor and2pixel same-peak neighborhood are preserved.

## Independent image evidence

| PTS | Domain0 NCC / competitors | Domain4 NCC / competitors | Locally unambiguous domains | Distributed support |
| --- | --- | --- | ---: | --- |
| 4.102669 | 0.996715 / 0 | 0.993951 / 0 | 2 | False |
| 4.119336 | 0.998708 / 0 | 0.995436 / 0 | 2 | False |
| 4.136003 | 0.943096 / 0 | 0.973466 / 0 | 2 | False |
| 4.152669 | 0.951866 / 0 | 0.968661 / 2 | 1 | False |
| 4.169336 | 0.959535 / 0 | 0.968362 / 0 | 2 | False |

Domain0(upper-left reviewed wall) is unique within the declared local lattice on all five images and has NCC>=0.943096. Thus absent tracked upper corners does not mean no upper-domain image structure. Domain4is also locally unique on four images, but has two qualified alternatives at4.152669. The other regions contain5–39competing positions depending on image/domain; a strong whole-domain score cannot be counted as independently localized correspondence. At phase disappearance domain1projection intersects protected phase pixels, so its full-footprint score is withheld rather than trimming the source population.

## Continuity decision

This is additional appearance evidence for visible scene continuity across the transient UI, not a production continuity decision. Individually unambiguous domains never meet the three-cell/two-row/two-column quorum. Finite local translation search cannot rule out larger displacements, affine alternatives, a scene-preserving edit, or small foreground contamination. Missing support remains unknown. No qualification/event follows.

## Contract change

A passive pure image audit is added outside production. It compares complete source footprints and rejects any projection/interpolation tap outside bounds or entering protected timer/phase pixels. It emits appearance/ambiguity statistics, never background masks or runtime proofs. No original tracker decision, threshold, sampler, GT or assertion changes.

## Tests

Four focused tests pass in1.05seconds: distinctive random image, repeated smooth gradient ambiguity despite high NCC, flat/unrelated input abstention, and exact invariance to protected UI changes. Ruff passes the new code/tests. Existing71related tests previously passed on unchanged code; production mypy104file result remains applicable because no production files changed.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Same-input unchanged tracker support | 22/29 | 22/29 | 0 |
| Critical images with independently localized domain quorum | Unmeasured | 0/5 | Unmeasured |
| Qualification/runtime events from this experiment | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | Historical23/55/4 | Not rerun | Unmeasured |
| Canonical negative / discontinuity violations | Historical0/0 | Not rerun | Unmeasured |

30-frame replay plus five domain audits completed in 12.717765seconds. Instrumentation differs from prior measurements, so no speed-improvement delta is claimed.

## Remaining blocker

Independent domain acceptance is rejected as sufficient. The upper distinctive structure supplies a useful constraint, while several individually ambiguous domains may still support a unique joint camera hypothesis. Next test joint multi-domain displacement consistency with the unchanged original projection, explicit competing distributed hypotheses and complete footprint accounting; do not choose a better offset to repair this run or count each ambiguous region as an independent match. Freeze that contract before independent holdout/negative qualification. Current semantic occlusion eligibility, source-safe bootstrap and paired scene/UI qualification remain incomplete. R1stays first priority; R2/result-banner work and full E2E remain gated. All82historical assertion rows are unchanged. No Windows execution is claimed.
