# Development study: remaining score rejections and incomplete captions

The independent End-display miss at1507.716667s remains a failure. This study uses only the original development intervals354–362,444–452 and518–526s. It opens no new held event and does not change production readers, profiles, thresholds, timing or qualification. Code fingerprint remains `d14e4b78b3e1fae4df0d154d21067b452796794a9c954992cf7f2ebb12a6d091`; profile remains `6411f7d326f71076efa54bb431a8efc501d01678fccd19a1f3a07a62c2146c80`.

## Reproduce the source of unknown scores

Fresh current-frame reader calls verify each cached full-image pixel hash. Across2,886 development score-field calls,2,780 are accepted and106 unknown. Unknown reasons:52 extra-component counts,29 foreground touching the ROI border,23 digit-layout inconsistency and2 below NCC0.90. Thus relaxing the confidence floor would address almost none of the observed rejections and is not attempted. These are accepted/unknown counts, not independently labelled accuracy.

One fixed private prototype applies the existing small, vertically separated speck-removal rule to interior components as well as border components. Complete centered core glyphs, alignment, separation, size and area limits remain the same; no parameter sweep, value hint, temporal repair, history, fallback or retry is introduced. All ten digit classes still compete at NCC0.90 and class margin0.04. This is a changed preprocessing hypothesis and requires separate evaluation; it is not represented by the unchanged production fingerprint alone. Its exact implementation hash is71538662df0e0405bf23c4ba0ed04f822b3034736548554bc2d585c4427db774.

The2,780 previously accepted values **and confidences** remain exactly identical. Seven formerly unknown fields become readable and99 remain unknown. Assistant review of the original development crops reads1,2,2,3,2,2,2, matching all seven new outputs. This is development review after prediction, not independent human annotation or qualification. Thirteen clean/noise synthetic equivalence cases and four missing-leading-digit/internal-fragment rejection cases pass. Synthetic controls do not establish safety over real scene backgrounds or all damaged digit shapes.

The source inventory takes29.495s and prototype evaluation30.160s. Two diagnostic harness attempts failed before a complete inventory: one used an incorrect result-field name and the other an undersized montage canvas. Correcting those harness mistakes changes neither the production reader nor the proposed preprocessing. Their failed outputs/logs remain private and separate from the completed run.

## Early caption review

A source-only contact sheet samples the original LOST development context every0.2s from355.6 through359.4s. The earlier animation contains lines and incomplete/red glyph fragments before a complete white LOST display. Those fragments are not accepted as complete-caption positives. This bounded visual review does not assert exhaustive first-complete-caption timing and does not justify a longer End deadline.

## Decision and next gates

Do not promote this prototype based on seven development recoveries. The held miss has two obstacles—interrupted score evidence and late complete result—and this study does not prove either is resolved by a valid complete End path. Preserve the failure and its immutable source target. No current held event is reopened, no native event is synthesized, and the rejected temporal score-restart method stays rejected.

Before promotion, require adversarial real-source negatives and clipped/missing/misaligned glyph controls, current native execution under an explicit changed-method identity, and a different source-reviewed event selected after method freeze. Existing held images are exposed for subsequent changed methods. Formal End and full lifecycle qualification remain incomplete. The aggregate is `e2e_reports/match_001/score_separated_speck_development_study.json`; private source images, masks, labels and raw predictions remain outside Git.

## Exposed source controls and negative-label correction

A fresh source-owned decode of the four previously exposed windows1800/1830/1860/1920s,0.3s each, supplies76 frames/152 score-field calls. All114 previously accepted values/confidences remain identical;32 stay unknown and6 become readable. A separate source-only replay reproduces all six full-frame pixel hashes exactly. Assistant review reads10,10,11,11,12,12 and agrees with all six new outputs. This is exposed source review after predictions, not independent accuracy evidence. Controls take41.726s; exact-image replay is additional unmeasured time. No End tracker or formal lifecycle is evaluated in this score-only experiment.

The1920s source shows ally11 at1920.116667s, then12 at1920.216667s and1920.283333s; the center changes from Spike to0:06 and enemy remains10. Thus the historically named fixed-negative window is **not a pure End-negative interval**. This source-display observation does not establish an internal End time, but it invalidates using this window as a clean negative. The earlier reports already withheld formal false-positive-rate claims; keep their raw predictions and hash identities unchanged and read their zero-End counts as mixed-scene diagnostic controls. Do not use this now-exposed event as blind evidence for any changed method.

The prototype remains unpromoted despite13 source-reviewed recoveries across development and exposed controls. Real-scene safety, the full native temporal path and a new independent event remain required. Source crops and raw rows stay private. The final source-control review also had an undersized montage-canvas failure; a replay with corrected canvas width verifies the same six source pixel hashes without changing recognition.
