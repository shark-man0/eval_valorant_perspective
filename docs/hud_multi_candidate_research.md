# Offline HUD multi-candidate comparison

This research API preserves the production Reader, Geometry, thresholds and
event contracts. It emits unconfirmed Score hypotheses, not Player Facts or
formal Round boundaries. It never fills a character from a previous frame.

`scripts/diagnostics/score_hypotheses.py` exposes:

- `generate_score_hypotheses(inner_roi, strict_reader)`: four foreground paths
  (row contrast, native border, white foreground, local top-hat). All ten digit
  templates remain competitors. Suspicious border/components stay flagged in
  the research results. Single components and adjacent pairs form bounded
  alternative segmentations; no absent glyph is synthesized.
- `rank_score_hypotheses`: NCC, edge, coverage/NCC or externally supplied
  learned scores, on the same candidate set. Scores are not probabilities.
- `selective_score`: preserve the existing Geometry-admitted baseline, with
  a separately measured recovery proposal. Recovery requires unchanged .90
  similarity/.04 class gap, complete foreground and layout, no border clipping,
  two extraction paths and no competing supported text. Those correlated
  extraction paths are not independent semantic evidence.

The caller must reuse registry admission and `hud_feature_contract.verify_patch`
before supplying a crop. Bind every report to source SHA, physical group, native
PTS/timebase/epoch, encoded and pixel hashes, ROI and Profile fingerprint. Some
cached images already contain the Profile subregion: cropping it twice is an
input-contract error. Never connect sparse acquisition epochs into a boundary.

Budgets: <=262,144 native ROI pixels, four masks, <=8 components per mask,
<=16 segmentations per mask, all ten digit classes, top five strings per
segmentation and <=20 unique output strings. Large/empty/invalid inputs fail
before matching. Memory/time remain bounded; output includes raw class scores,
component boxes, discarded foreground and rejection flags. Zero proposals is
valid. Retain the unchanged baseline even if the proposal cap misses it.

## Fixed DEVELOPMENT findings

Comparison reused 248 cached Score fields from 14 physical DEVELOPMENT sources.
Human text existed for 74 fields: 32 previous fields and 42 additional fields.
All ten digits occur; only seven additional fields are two-digit. The former
ten-field fixed test is already exposed development data. No new labels or
independent qualification were created. All fit parameters/learned features
were reused unchanged; this study did not train another model.

| Method, additional 42 Human fields | Correct | Wrong proposal | UNKNOWN |
|---|---:|---:|---:|
| Existing Reader, before Geometry | 38 | 0 | 4 |
| Broad candidates, NCC top-1 | 34 | 8 | 0 |
| Same candidates, foreground coverage/NCC | 40 | 2 | 0 |
| Existing spatial SSL + Human readout rerank | 32 | 10 | 0 |
| Existing generic features + Human readout rerank | 38 | 4 | 0 |
| Safety path, including unchanged Geometry | 37 | 0 | 5 |

NCC candidate hits at 1/3/5: 34/40/40 out of 42. The proposal cap contains the
Human text in 40/42 fields. A higher retrieval hit count is not accepted-score
accuracy. NCC top-1 dropped a digit in all seven two-digit fields; the explicit
coverage intervention reduced drops to one. It preserved all previous correct
fields, but turned UNKNOWN into one wrong proposal in the old 32-field set and
two wrong proposals in the additional set. The former ten-field test reached 10/10
raw hypotheses, but these errors prevent adoption. Do not tune that
exposed subset until it passes.

The safe path recovers no additional accepted text and is identical to the
baseline including Geometry. Keeping safety does not establish a recognition
improvement. All learned/unguarded replacements remain rejected.

Controlled diagnostics: blank three plus truncated digits ten produced 11
numeric hypotheses, but zero safe recoveries. This is not a real-video negative
denominator. Real background/occlusion/no-Score states lack confirmed labels.
The existing 73 lifecycle inputs remain exactly unchanged, with confirmed
natural End and Start false establishments each 0/11. No new internal event
time, human boundary or formal End/Start was created.

Private source images, labels, models, candidate rows, native timing and Terra
contact sheets remain outside Git. A training-only anonymous Terra batch is
prepared separately; no Terra call or transfer is implied by that preparation.
Any Terra feature comparison remains unexecuted until an actual response is
provided through the user-selected session with transfer approval.

## External references

- [OpenCV 4.11 morphology tutorial](https://docs.opencv.org/4.11.0/d3/dbe/tutorial_opening_closing_hats.html)
  supplies the top-hat operation used as the fourth ablation path. No tutorial
  images or code are copied into training.
- [Riot VALORANT developer documentation](https://developer.riotgames.com/docs/valorant)
  describes the public content catalog and use policies, not a current Score
  glyph GT set. No catalog was downloaded or treated as permission to train.
- [Official patch 0.49](https://playvalorant.com/en-us/news/game-updates/valorant-patch-notes-0-49/)
  records observer HUD visibility changes. This historical fact supports keeping
  view/HUD states uncertain; it does not label a particular modern recording.

Next work should address fragmented foreground and rejection on representative
real non-Score/occluded examples. A larger candidate list, low supervised loss
or successful CI does not demonstrate a better Reader.
