# R1 continuous native source analysis

## Problem

R1 lifecycle needs continuous native evidence, not isolated review frames. The earlier 30-frame source replay began at 3.902669 seconds; it did not cover the requested 3–6 second interval. A qualified scene transport API exists, but actual source/UI qualification and native lifecycle integration are incomplete.

HEAD: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.
Target remains `GT-R1-ROUND-START`, with downstream round count/order/package assertions. No assertion data enters the source measurements.

## Evidence

[The frozen declaration](../e2e_reports/match_001/r1_continuous_source_declaration.json) fixes source video SHA256, common production code, reviewed source assets, integer frame spacing and explicit 3–6 second input. [The actual native run](../e2e_reports/match_001/r1_continuous_source.json) decodes every selected frame through `VideoService.native_window`, verifies source/native PNG hashes and evaluates the unchanged common source episode. It completed in 154.471710 seconds, exit 0.

There are 180 frames, actual PTS 3.002669–5.986003 seconds, ticks 46121–91945, spacing 256, time base 1/15360. The declaration finds 144 known-exposure overlaps; the remaining frames are not automatically holdout. This entire investigated sequence is development evidence.

| State / reason | Frames |
| --- | ---: |
| Initialization pending | 53 |
| Observed seed at 3.886003 s | 1 |
| Descriptive adjacent scene links, 3.902669–4.202669 s | 19 |
| Seed model incoherent, 4.219336 s | 1 |
| Episode terminated, 4.236003–5.986003 s | 106 |

There is no rejoin, qualified proof or event. The descriptive links span the already-reviewed panel removal and transient clock/view-model presentation. This does not qualify either semantic UI absence or uninterrupted content.

## Competing hypotheses

1. The background source breaks at the tracking stop.
2. Original-reference-to-current motion becomes incompatible with the long-lived model while adjacent correspondence remains supported.
3. A different initial observation changes the long-term feature history and hence the stop point.

[The observational replay](../e2e_reports/match_001/r1_continuous_seed_failure.json) instruments existing `ReviewedWorldChain` model/region sinks without changing computation. All 21 replayed seed/link/stop outputs match the original run exactly. All 58 candidate patches at the stop have adjacent NCC ≥0.90; minimum is 0.908739. Candidate distribution: regions 1/2/5 contain 3/34/21 points. The original seed partial-affine RANSAC accepts 52/58 = 89.6552%, below the unchanged 90% floor. Six rejected points belong to region 2.

## Independent image evidence

[The same-correspondence motion comparison](../e2e_reports/match_001/r1_continuous_seed_model_comparison.json) fits the stored image-derived points, without timer/phase pixels or values. Each fit uses OpenCV RANSAC, RNG seed 0 and the same 2 canonical-pixel reprojection threshold. Full affine is only a competing diagnostic model; it is not adopted.

| Source points → current | Inliers | Ratio | Maximum final residual, px |
| --- | ---: | ---: | ---: |
| Original seed, partial affine | 52 / 58 | 89.6552% | 2.035263 |
| Original seed, full affine | 47 / 58 | 81.0345% | 2.873581 |
| Previous native frame, partial affine | 58 / 58 | 100% | 0.322081 |
| Previous native frame, full affine | 56 / 58 | 96.5517% | 0.298834 |

The reported inlier masks are the estimator's actual outputs, not reclassified using final residuals. The full affine result does not justify switching to a more flexible seed model. Adjacent correspondence supports hypothesis 2 at this stop; it does not exclude a background-preserving edit or authorize the initial foreground transition. Unwarped/warped appearance, feature correspondence and foreground presentation remain distinct evidence.

Reproduce the source replay:

```bash
python3 scripts/diagnostics/audit_native_seed_failure.py \
  --source-report e2e_reports/match_001/r1_continuous_source.json \
  --scene-profile outputs/recognition-investigation/world-domain-bootstrap-20261009/profile.json \
  --output /tmp/r1-seed-failure-new.json
```

To reproduce motion comparisons, use the final row's `seed_model[0]`: fit `seed_points` or `previous_points` to `current_points` with `cv2.estimateAffinePartial2D` or `cv2.estimateAffine2D`, `method=cv2.RANSAC`, `ransacReprojThreshold=2`, after `cv2.setRNGSeed(0)` for each fit. Preserve original inlier masks.

## Continuity decision

The stop reason is a failed long-term reference model, **not a demonstrated content discontinuity**. The sequence cannot be approved for lifecycle runtime: foreground continuity and independent source/UI qualification remain unresolved. Current fail-closed termination remains unchanged. No R2 or result-banner threshold work follows from this diagnostic.

## Contract change

No production contract is changed by this investigation. Future design must distinguish acquisition/reference identity validity, accumulated seed-to-current motion and adjacent content continuity. An incoherent long-term seed model cannot by itself become a positive cut label; equally, a coherent adjacent model cannot bypass world eligibility, appearance, negative controls or temporal source ownership. Do not reseed or join a terminated episode to manufacture coverage.

## Tests

The new diagnostic runner passes Ruff. Observational replay preserves all 21 actual production outputs exactly and terminal-verifies all 180 source images, source report, scene assets and HUD source code. There are no production source edits in this follow-up. The preceding unchanged production tree passed 65 related tests (35.44 s), Ruff and mypy (113 files). Synthetic positive transport tests are not image qualification.

## Previous / Current / Delta

| Metric | Previous short R1 window | Current 3–6 s window | Delta |
| --- | ---: | ---: | ---: |
| Native decoded frames | 30 | 180 | +150 (different input) |
| Initial observed seed, s | 3.902669 | 3.886003 | −0.016666 |
| Descriptive scene links | 22 | 19 | −3 (different seed/history) |
| First tracking stop, s | 4.286003 | 4.219336 | −0.066667 |
| Adopted real paired scene/UI qualification | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 archived | Unmeasured | Unmeasured |

The stop/history difference demonstrates sensitivity to the initial source context, not a canonical regression measurement. The 154.471710 s runtime covers a different input and cannot be called an acceleration or slowdown against a short saved-frame replay. Full E2E was not run: the required independently qualified three-boundary candidate is absent. Negative/discontinuity canonical results remain unmeasured, not newly claimed zero.

## Remaining blocker / next task

Investigate a source contract separating original feature identity and current/adjacent motion under independently reviewed image controls, before deciding whether production source tracking can change safely. The actual initial foreground transition is still not classified as normal animation versus background-preserving content jump. Current-image purchase-panel disappearance also lacks independent qualification. After those are established, deliver native timer/phase/source evidence through the system lifecycle and event/package/trace contracts; player-owned facts must remain identity-gated. Canonical acceptance and Windows runtime verification remain outstanding.

## Follow-up: independent appearance at the stop

[The fixed adjacent-model appearance audit](../e2e_reports/match_001/r1_seed_stop_adjacent_appearance.json) compares native ticks64553→64809 (4.202669→4.219336 s), using the already recorded previous-to-current partial-affine model. It does not refit against image-match scores. Actual decoded/encoded hashes and the source/model reports are checked before and after measurement. The unchanged common engine evaluates all 289 offsets for each of the six declared non-timer/non-phase domains (1,734 measurements), preserving exclusions, complete footprints, unknown competitors and the existing0.90floor.

| Reference domain | Fixed adjacent projection NCC |
| --- | ---: |
| 0 | 0.973564 |
| 1 | 0.996500 |
| 2 | 0.999580 |
| 3 | 0.986984 |
| 4 | 0.974923 |
| 5 | 0.998871 |

All six domains support the fixed transform, source/current witnesses remain spatially distributed, and the declared local lattice contains no joint competing offset or unresolved alternative. Runtime2.114126s. This is independent photometric corroboration of the existing adjacent-point geometry at the tracking stop, not merely a second fit of those points. Its scope is the visible background under the frozen model/lattice, not all possible camera models, invisible elapsed game time or whole-scene semantic qualification. It does not reopen the terminated episode.

Native whole-image review covers ticks59689/64809/68905. At64809, the source domains remain wall/ground areas and the foreground weapon pose differs from the original seed. At68905, camera motion has exposed the doorway and a player on the right. A source reference alone cannot supply world eligibility for arbitrary later views.

| Stop-link evidence | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Geometrically coherent adjacent points | 58 / 58 | 58 / 58 | 0 |
| Independently measured supporting background domains | Unmeasured | 6 / 6 | Not comparable |
| Qualified runtime scene evidence | 0 | 0 | 0 |
| Rejoined terminated episode | 0 | 0 | 0 |

## Follow-up: client graph history hypothesis rejected

A new independent-source hypothesis was that client FPS graph history could discriminate UI presentation from a content jump. [The fixed color probe](../e2e_reports/match_001/r1_client_graph_history.json) evaluates all180 saved native images without reading timer/phase values, GT or assertions. Bounds[1766,235,1876,270] exclude the fixed outer border, title and outer numeric labels. Signed BGR arithmetic selects blue/green channels exceeding red by20 and each exceeding120. These are descriptive probe parameters, not an acceptance threshold or a graph recognizer. They were fixed before the recorded run; no post-result parameter tuning follows.

At4.102669s the color silhouette is identical to the previous frame. At the first transient4.119336s it has232selectedpixels,116changedpixels and NCC0.754216. At4.136003s NCC0.948809; at4.152669s the probe is identical to its predecessor. These numbers do not establish whether the graph updated normally or the source jumped.

More importantly, the fixed probe selects2,871pixels at4.486003s and3,368pixels at4.502669s, out of3,850pixels in the ROI. Native image review at4.486003s shows cyan doorway/weapon effects visible through the transparent graph. The probe measures underlying scene colors as well as the plotted line. Thus neither low NCC nor silhouette persistence supplies an independent graph-history contract. Reject color-only graph extraction as a continuity witness; do not add it to qualification or tune it until the first transient passes. A reliable graph witness would require separate plot/background discrimination and independent negative controls.

The recorded probe completed in24.439158s with exit0. This is saved-image diagnostic runtime, not targeted/sample/full E2E runtime. Ruff passes including the new diagnostic script and unchanged production tree. No production code, profile, sampler, assertion, GT or recognition threshold changed. Canonical Current/Delta remain unmeasured and all82 assertion records remain unchanged.

## Updated decision / next action

At the4.219336s tracking stop, independent point geometry and six-domain photometry jointly support visible adjacent background continuity despite long-term seed-model failure. No positive content-cut label is justified there. The initial R1 foreground/UI transition remains unresolved, and the graph probe adds no qualified evidence. Preserve fail-closed behavior. The next source design must separate long-lived reference identity from current-step camera evidence, while retaining appearance, current-world eligibility, native chain ownership and negative qualification; it cannot bypass them using this single successful stop-link audit. Native lifecycle, package/trace delivery and canonical acceptance are still unfinished.
