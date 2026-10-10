# R1 foreground correspondence analysis

## Problem

Distributed image evidence supports visible background continuity near R1, but the first transient frame also changes hand/knife presentation abruptly. Similar changes exist in an earlier purchase-phase sequence. The earlier fixed-region comparison did not account for pose alignment. Target remains `GT-R1-ROUND-START` and its round count/order/package dependencies; no actual boundary is emitted here.

HEAD: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.

## Evidence / competing hypotheses

1. A normal recurring view-model animation changes pose abruptly between recorded frames.
2. The video contains a background-preserving content jump.
3. The poses are visually similar but not related by a rigid2Dmodel at corresponding sample offsets.

Whole-native-image review covers earlier ticks30761/31017 and R1ticks63017/63273: both pairs change from an extended knife/left-hand presentation to a butterfly-knife/right-palm presentation. Earlier purchase-phase text remains visible. That context is not an independently established no-edit control. Additional reviewed R1frames67625/76841/91945 show subsequent camera/foreground motion into the doorway. These later views do not establish a separately qualified barrier-removal event at the earlier start.

## Independent image evidence

[The declaration](../e2e_reports/match_001/r1_foreground_correspondence_declaration.json) fixes the existing three regions[940,750,1120,850],[1080,600,1190,740],[1440,930,1600,1050], without recropping after previous failure. These regions exclude timer and purchase-phase pixels. Four successive earlier post-pose frames are paired with four successive R1post-pose frames; two visibly mismatched pose pairs are recorded separately. Source/parent reports and encoded/decoded native hashes are bound and rechecked at completion. All inputs have already been exposed; this is neither blind holdout nor a source-cut qualification corpus.

[The result](../e2e_reports/match_001/r1_foreground_correspondence.json) uses GFTT100/quality0.01/distance5, reciprocal LK21×21/pyramid3/error≤1nativepixel,15×15patchNCC≥0.90 with the existing masked contrast floor5, and partial-affine RANSAC2nativepixels/consensus≥0.90. No whole-crop maximum-score optimization, threshold change, clock/phase value or Validation Pack enters scoring.

| Earlier tick → R1tick | Patch correspondences | RANSAC inliers | Consensus | Geometric quorum |
| --- | ---: | ---: | ---: | --- |
| 31017 → 63273 | 85 | 74 | 87.06% | No |
| 31273 → 63529 | 31 | 20 | 64.52% | No |
| 31529 → 63785 | 23 | 9 | 39.13% | No |
| 31785 → 64041 | 24 | 17 | 70.83% | No |
| 30761 → 63273, different poses | 0 | 0 | Unavailable | No |
| 31017 → 63017, different poses | 0 | 0 | Unavailable | No |

The first same-pose hypothesis has accepted patch correspondences in all three regions, minimumNCC0.900146, but fails the existing globalconsensusfloor. Subsequent pairs do not form a stable matching trajectory. Visually different pose controls produce no accepted patches, but this does not demonstrate ability to reject real content edits. The regions contain mixed image pixels and are not an independently qualified foreground mask.

The initial exploratory read used `cv2.imread(...,0)` and yielded76/85inliers. The bound replay uses nativeBGR→`cv2.cvtColor(...,COLOR_BGR2GRAY)`, matching the production image path, and yields74/85. Do not select the more favorable conversion or present either as passing: both fail0.90. Source decoder/image normalization is part of the evidence contract.

## Continuity decision

The results support limited pose-appearance similarity. They do not prove a normal recurring animation, establish an animation whitelist or classify the R1source as unedited. A rigid2Dmodel's failure also cannot by itself prove a content cut for a deforming3Dview-model. R1foreground/source-continuity qualification remains unresolved; retain fail-closed lifecycle behavior.

## Contract change

Only a diagnostic runner and its tests are added. Production recognizers, geometry/ownership/discontinuity policy, references/profiles, GT/assertion semantics and full sampler are unchanged. No runtime scene/UI proof, boundary, player-owned weapon/HP/death/shot fact or qualification is generated. Pose-matching dictionaries cannot be supplied as trusted lifecycle inputs.

## Tests

Three diagnostic tests pass in1.19s: perfect image correspondence still grants no runtime/foreground authorization; mutated timer/phase pixels do not affect declared pose-region results; unrelated images produce no supported structure. Ruff passes for `src tests scripts/e2e` and the new runner. Existing113-fileproductionmypy coverage remains unchanged; WindowsOpenCV/native decoder execution is unverified.

```bash
python3 scripts/diagnostics/compare_native_pose_correspondence.py \
  --declaration e2e_reports/match_001/r1_foreground_correspondence_declaration.json \
  --output /tmp/r1-foreground-correspondence-new.json
```

The declaration requires its exact frozen files. If changing the method, preserve this rejected result and create a new explicit declaration; do not rewrite historical hashes to imply independent qualification.

## Previous / Current / Delta

| Metric | Previous fixed-ROI comparison | Current correspondence investigation | Delta |
| --- | --- | --- | --- |
| Earlier pose proves normal R1animation | Unproved | Unproved | No qualified gain |
| Same-pose trajectory pairs tested by fixed method | Unmeasured | 4 | New diagnostic coverage |
| Qualifying geometric pairs | Unmeasured | 0 / 4 | Not comparable |
| Adopted scene/UI qualification | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 archived | Unmeasured | Unmeasured |

No new standard targeted/sample/full E2E ran, no completed phase or PASSgain is claimed, and all82archived assertion records are unchanged. Full E2E remains unjustified without independently qualified boundary inputs.

## Remaining blocker

Current image evidence has not distinguished normal view-model presentation from a background-preserving source jump. A question about the existing video's provenance (unedited continuous recording versus edited footage) is pending; no extra video is required by this investigation. Such provenance would inform review, not automatically qualify the detector, become GT timing or authorize player facts. Independent source/world/UI qualification and the native lifecycle/event/package/trace integration still remain necessary.
