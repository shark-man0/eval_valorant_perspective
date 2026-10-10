# Frozen native source entrance cohort

## Problem

The original observed R1 chain supports 22 native links, including phase disappearance and the first transient display, before permanent termination at 4.286003 seconds. These are descriptive measurements, not qualified continuity proofs. Production paired scene/UI authorization remains unavailable. Target remains R1 start and its lifecycle count/ordering dependencies.

## Evidence and change

HEAD `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`. [The refreshed inventory](../e2e_reports/match_001/native_exposure_pts_inventory_20261010.json) finds 433 saved unique native ticks, compared with 304 in the preceding inventory (+129). It remains a conservative known-exposure inventory, not proof of exhaustive exposure. Reports without integer source ticks can be underrepresented.

[The pre-decode declaration](../e2e_reports/match_001/native_scene_entrance_cohort_declaration.json) selects 5.4–5.6 seconds after the previously saved contiguous R1 tick range ends. It freezes the runner, source video, source profile/assets, production recognizer fingerprint, inventory inputs, all 433 known ticks and 1,961 known native pixel hashes before decode. No GT, timer value or expected event timestamp selects or enters the recognizer.

The runner uses `VideoService.native_window` and `observe_native_scene_window`, preserving full integer-PTS native coverage, source-owned decoder epoch and unchanged common scene algorithms. It saves lossless source images locally for subsequent review. Deferred initialization is explicitly frozen; no previous image history exists while initialization is pending. Every source/code/image dependency is verified at completion. Source sampling for canonical full E2E is unchanged.

## Independent image evidence

[The measured cohort](../e2e_reports/match_001/native_scene_entrance_cohort.json) contains 12 native frames, ticks 82985 through 85801, step 256, time base 1/15360. All 12 have zero known PTS/pixel exposure overlap. All 12 remain `image_supported_initialization_pending`: no scene seed and no frame-pair continuity evaluations are established.

Full native first/last image review shows a camera view away from the original close-wall reference, with a doorway/room background and multiple players. This gives an image-based scope explanation for unavailable reference acquisition; it is not a proven code-level attribution to a specific rejected anchor. No character or dynamic crop is relabeled as static world support to make this cohort pass. First/last review does not label every intervening frame as continuous.

## Competing hypotheses and continuity decision

The frozen reference's source-appearance coverage is insufficient for this different view. This result cannot quantify the scene-tracking accuracy after initialization, because initialization never occurs. It cannot be reported as zero wrong detections, zero false positives, successful holdout or evidence of a content cut. Qualification stays withheld. Do not add arbitrary nearby cohorts or reference banks merely to obtain three successful counts.

## Contract change

Only diagnostic orchestration is added. Native production decoder/scene APIs, thresholds, reviewed-world policy, permanent termination, UI qualification, ownership and assertions are unchanged. No scene/UI proof, event, package or player-owned fact is emitted.

## Tests

Two new file-binding tests reject changed and missing frozen inputs. Together with native scene input/source-binding tests: 15 passed in 12.54 seconds. Ruff passed for `src tests scripts/e2e` and the new runner; mypy passed for all 112 source files. `git diff --check` passed. No full E2E candidate was created.

## Previous / Current / Delta

| Metric | Previous R1 entrance verification | New independent-context cohort | Delta |
| --- | ---: | ---: | ---: |
| Frames | 30 | 12 | -18 |
| Descriptive scene links | 22 | 0 | -22 |
| Known exposure overlap | Exposed development | 0 frames | Not comparable |
| Qualified continuity producers | 0 | 0 | 0 |
| Runtime seconds | 70.662816 | 21.808556 | -48.854260 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | Unmeasured | Unmeasured |

Different inputs and numbers of frames make these descriptive count/runtime differences unsuitable as accuracy or speed improvements. Canonical negative/discontinuity counts, round events and packages are unmeasured for the new cohort. All 82 archived assertion entries are unchanged.

## Remaining blocker

Real source acquisition coverage must be qualified separately from image-to-image tracking and phase disappearance. The current one-view reference is suitable for descriptive R1 experiments but has not established independent source coverage. Paired producer installation and native-to-lifecycle merge remain incomplete. Reassess reviewed source acquisition scope and controls before creating more appearance variants; preserve unknown for unsupported views. Windows native decoding and this cohort have not been executed on Windows.
