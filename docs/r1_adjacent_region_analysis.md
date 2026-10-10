# R1 adjacent native-region analysis

## Problem

R1 still lacks independently qualified source/UI continuity. A repeated-pose rigid-affine comparison failed; matching background appearance alone cannot explain the simultaneous foreground change. Target remains `GT-R1-ROUND-START` and its downstream count/order/package predicates. No R2/end tuning or recognizer adoption occurs here.

HEAD: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.

## Evidence

[The declaration](../e2e_reports/match_001/r1_adjacent_regions_declaration.json) fixes the existing six wall-domain boxes, scaled from 640×360 to native coordinates, and the existing three mixed foreground boxes. All 180 saved native frames in the 3–6 second window are processed, yielding 179 adjacent pairs. Source report, every PNG, decoded pixels, video hash, exact PTS/time base, uniform cadence and single decoder epoch are checked; file bindings are checked again at completion. Timer/phase regions are excluded before any image measurement. Neither Validation Pack nor timer values are scoring inputs.

[The measurements](../e2e_reports/match_001/r1_adjacent_regions.json) are exposed development evidence. Fixed boxes are candidate regions, not qualified world/foreground masks. In particular, their original world-membership review does not authorize those boxes throughout all 180 frames: later camera/weapon movement can enter them.

## Competing hypotheses

- Continuous camera/background with an abrupt normal view-model animation and transient UI.
- A background-preserving source cut or elapsed-time jump.
- A scene-wide visual replacement.

The first two remain unresolved. Absence of a detectable background change cannot establish the absence of an edit.

## Independent image evidence

NCC uses native BGR→grayscale conversion and no camera warp. The changed-pixel statistic is the fraction whose maximum absolute BGR-channel difference is at least 8; this is an existing descriptive measurement, not an acceptance threshold.

| Current native tick | Time (seconds) | Minimum scene NCC across six candidate background regions | Changed fraction in three mixed foreground regions |
| --- | ---: | ---: | --- |
| 63017 | 4.102669 | 0.992527 | 0 / 0.002922 / 0.006615 |
| 63273 | 4.119336 | 0.995074 | 0.694278 / 0.780195 / 1.000000 |
| 63529 | 4.136003 | 0.921992 | 0.515278 / 0.631429 / 0.633594 |
| 63785 | 4.152669 | 0.942158 | 0.300444 / 0.650844 / 0.701042 |

The phase-panel disappearance independently measured at tick63017 precedes the abrupt foreground change by one native frame (256 ticks at 1/15360). The first transient display at tick63273 coincides with foreground change, while all six background regions retain high unwarped scene NCC. Timer labels here are only a post-measurement association with the previous diagnostic; they do not drive region scoring.

The two existing NCC contracts have different contrast floors. `scene_domains._ncc` uses standard deviation ≥1; `weapon_identity.masked_score`, also used by semantic references, uses ≥5. Both are recorded separately. At tick63273, all six regions satisfy the scene floor, but only two satisfy the masked-reference floor. Four regions have previous/current standard deviations near 1.59, 3.79, 1.33 and 1.83. It would be incorrect either to declare their scene measurements rejected under a newly imposed floor5, or to promote them to usable masked semantic references based on scene NCC. No production contrast policy changes.

Across the 179 pairs, the counts of background regions satisfying both images' masked-reference contrast floor5 are: 2 regions on29pairs, 3 on9, 4 on3, 5 on29 and 6 on109. This is a contrast-availability distribution, not continuity accuracy or semantic coverage. Large foreground changes also occur elsewhere; neither their frequency nor these unlabeled examples proves a normal animation.

## Continuity decision

The transition is not timer-only: three foreground regions change strongly at the first transient image. Distributed background agreement argues against a visible scene-wide replacement in these regions, but cannot distinguish normal foreground presentation from a background-preserving cut. Keep continuity unresolved and fail closed for actual lifecycle authorization. Do not reset or confirm a production lifecycle solely from these measurements.

## Contract change

Diagnostic only. Each result explicitly withholds source-continuity classification and runtime authorization. No qualification, reference/profile, owned player evidence or system boundary is generated. Existing scene/masked contrast policies, NCC0.90, geometry, identity, ownership, OCR, discontinuity, full sampler, Validation Pack and assertion semantics remain unchanged. No fixed offline PTS becomes a production trigger.

## Tests

Five new diagnostic tests pass in0.41seconds. They verify that excluded phase/timer pixels cannot affect measurements, a flat image yields unknown NCC, matching images grant no authorization, and invalid/excluded boxes are rejected. Ruff passes for `src tests scripts/e2e` and this runner. Production code is unchanged by this follow-up; the previous 116-file mypy and 227-test verification remain historical, not newly rerun checks. Windows OpenCV execution is unverified.

Reproduce to a new output:

```bash
python3 scripts/diagnostics/audit_native_adjacent_regions.py \
  --declaration e2e_reports/match_001/r1_adjacent_regions_declaration.json \
  --output /tmp/r1-adjacent-regions-new.json
```

Runtime38.939209seconds covers saved-image measurement and terminal binding checks, not decode or canonical E2E.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Complete fixed-region adjacent appearance sweep | Unmeasured | 179 pairs / 180 frames | New coverage |
| Actual source/UI qualification adopted | 0 | 0 | 0 |
| Runtime boundaries emitted by this diagnostic | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 archived | Unmeasured | Unmeasured |
| Canonical negative failures / discontinuity violations | 0 / 0 archived | Unmeasured | Unmeasured |

The archived canonical report remains23PASS/55FAIL/4NE,4634frames and12995.972856seconds. No fresh targeted/sampled/full E2E or canonical regression measurement is claimed. Full E2E is unjustified without qualified actual boundary evidence. All82archived assertion entries remain unchanged.

## Remaining blocker

A reviewed source/foreground temporal contract must distinguish the first two hypotheses before accepting R1; current same-video images are not independent normal-animation labels. The pending provenance question concerns this existing source, not a mandatory additional video. Provenance alone would still not qualify the recognizer. Separately, the positive phase-absence reference remains unsupported by the near-flat panel background. Do not repeat flat-background references, rigid pose variants or loosen thresholds. Native API-to-package/trace transport exists but automatic native streaming and real qualification remain incomplete. The goal and conditional30PASS milestone are not achieved.
