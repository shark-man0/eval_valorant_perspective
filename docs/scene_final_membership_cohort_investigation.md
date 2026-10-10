# Frozen R1-adjacent scene-chain cohort

## Problem

The final-membership diagnostic supports the critical R1 timer transition on development images, but cannot be installed as a qualified generic scene producer from that result alone. This checkpoint tests the frozen method on different nearby camera poses. Main remains `03bfcbf945fbf3d7b04c54d80b3c5ff103475db0`; production is unchanged. The target remains source-backed R1 start and its upstream lifecycle contract, not clock-value fitting.

## Evidence

Before decoding, [the reservation](../e2e_reports/match_001/scene_final_membership_cohort_reservation.json) pins video, tracker, runner, preprocessing/extraction bytes, six footprints and exact configuration. A conservative inventory contains SHA256s of all2098previously archived PNGs, irrespective of whether they were actually reviewed. Three intervals2.5–2.7,3.0–3.2and5.2–5.4seconds were selected for separated early camera poses, not assertion timing or clock values. Each contains12native frames and11adjacent links. Every increment is256ticks in1/15360; no frame skipping or restart after abstention occurs.

[The terminal report](../e2e_reports/match_001/scene_final_membership_cohort_diagnostics.json) has36frames/33links,0supported links and0known PNG-byte overlaps. Source video and all method/source image bindings were checked before and after measurement. Runtime was35.234600seconds. PNG-byte disjointness does not prove decoded-pixel independence when encodings differ, or independence from the same recording. No qualification claim rests on that inventory alone.

## Competing hypotheses

- The refined-mask contract alone generalizes to arbitrary nearby poses: not established; all three chains stop at their first link.
- Missing support proves a cut: rejected. The independently reviewed full-context panels show continuous-looking motion, wall/doorway/corridor and animation, with no visible hard cut. Uninterrupted hidden game time remains unproven.
- Whole-crop coverage and world-only seed eligibility vary with camera pose: supported by different first-failure mechanisms below. This requires an explicit evidence-domain contract, not a lower NCC or coverage floor.

## Independent image evidence

All36frames were reviewed as576×324full-context panels, with three640×360seed-footprint overlays. This is contact-sheet review, not native-resolution pixel-level semantic qualification. See [the review ledger](../e2e_reports/match_001/scene_final_membership_cohort_review.json).

| Interval | First rejected PTS | First rejection | Independent contextual observation |
| --- | ---: | --- | --- |
| 2.5–2.7 | 2.519336 | original_world_support_insufficient | Seed crops appear wall-only; coherent retreat/knife animation.94original identities remain across all6regions, but all warped crop valid fractions0.728940–0.848885fall below0.90. Later arms can occlude world footprints. |
| 3.0–3.2 | 3.019336 | seed_model_incoherent | Fixed seed footprints already include knife/arms, moving player/nameplate and phase barrier. A generic world-only bootstrap is not attested. |
| 5.2–5.4 | 5.219336 | seed_model_incoherent | Seed footprints include knife/arms, moving teammates and a nameplate in the corridor view. They cannot inherit the development wall labels. |

Post-score passive rejection-stage measurement reproduces the frozen first-link image-result dictionaries after normal JSON normalization; no candidate is refitted. [Stage details](../e2e_reports/match_001/scene_final_membership_cohort_failure_stages.json) distinguish retained world-patch support from valid whole-crop coverage. The first comparison initially failed because in-memory cell tuples were compared directly with JSON lists; normalized comparison passes. It was a verification representation mismatch, not recognition drift.

## Continuity decision

None of the33links is qualified. The original training episode still supplies independent evidence for visible scene continuity across0:00→2:25→1:39; the new cohort does not revoke those observations or establish general source qualification. Unsupported images remain unknown. The two contaminated seeds are unsuitable positive examples; their abstentions are useful stress evidence but cannot be relabelled blind cut negatives. No false-positive rate is inferred from this cohort.

## Contract change

No production contract changes here. The new diagnostic orchestration enforces frozen source/code bindings, new-only output paths, full native coverage and terminal verification. Initial feature labels are explicitly hypothetical until reviewed. It never imports validation values or produces lifecycle events.

The next design task must separate:

1. Qualified source-world seed eligibility, which is not guaranteed by fixed non-timer rectangles at arbitrary camera poses.
2. Current-frame occlusion, so moving player/weapon/UI patches cannot attest the world.
3. Valid projected appearance support under camera motion, independently of retained source-feature geometry.

The existing90%valid-coverage floor and NCC0.90are not lowered. Generic tracker bootstrap is not authorized by manual wall labels from a different pose. Additional camera models or OCR candidates do not address these semantic deficiencies.

## Tests

28focused unit tests pass in5.59seconds, including new native-coverage skip/duplicate/reversal guards and mutated-file rejection. Ruff passes on `src tests scripts/e2e scripts/diagnostics`. The preceding fresh mypy check passed102source files; production bytes remain unchanged. [Verification](../e2e_reports/match_001/scene_final_membership_cohort_verification.json) records terminal bindings and the unchanged82assertion matrix. Windows execution remains unverified; the runner uses shared Python/pathlib/shutil/subprocess orchestration.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Development support | 22/29 | 22/29stored result | 0; no rerun |
| New frozen-cohort support | Not measured | 0/33 | Not comparable |
| New cohort native frames | Not measured | 36 | Not comparable |
| New cohort runtime | Not measured | 35.234600s | Not comparable |
| Qualification created | 0 | 0 | 0 |
| New runtime events | 0 | 0 | 0 |
| Canonical PASS/FAIL/NE | Historical23/55/4 | Not measured | Not measured |
| Canonical negative/discontinuity violations | Historical0/0 | Not measured | Not measured |

The cohorts use different images;22→0is not an accuracy delta on comparable input. No assertion becomes PASS based on the tracker experiment. Historical canonical results and all82stored assertion statuses remain unchanged.

## Remaining blocker

The fixed-footprint method lacks demonstrated coverage and generic world-only seed qualification. It is not adopted or tuned on this cohort. All newly exposed images are development if later used for design, and must not be reused as blind holdout. Preserve their terminal failure evidence, redesign the semantic bootstrap/appearance-support contract explicitly, then reserve genuinely separate qualification before activating a trusted scene/UI producer. R2 and result-banner evidence remain separate; no full E2E is justified before the real three-boundary gate. No fresh targeted, sampled or canonical full evaluation was run here.
