# Offline Result title-region diagnostic

The existing configured text subregion can clip the top of taller Result words.
A title animation can also move glyphs outside even the outer banner region.
This diagnostic adds an opt-in crop proposal inside the configured
`round_end_banner`; it does not change the production layout, profile, reader,
confidence threshold, lifecycle or default diagnostic method.

## Frozen comparison method

Use the existing native preflight evidence and `diagnose_result_text.py` CLI.
Keep video, native evidence, layout, OCR executable/model and method files private.
An example method file is:

```json
{
  "version": "semantic_result_ocr_diagnostic_v1",
  "language": "eng",
  "roi": "round_end_banner",
  "psm": 7,
  "minimum_confidence": 0.90,
  "preprocessing": "gray_v1",
  "subregion_norm": [0, 0, 1, 1],
  "region_strategy": "structured_title_v1"
}
```

```sh
python -m scripts.diagnostics.diagnose_result_text \
  --video /private/source.mp4 --native-run /private/native-evidence \
  --layout /private/hud_layout.json --method /private/method.json \
  --output-dir /private/new-result-diagnostic --tessdata-dir /private/tessdata
```

Without `region_strategy`, the existing configured subregion is used. Structured
selection requires the full outer banner, English Result vocabulary and PSM 7.
It groups white210 connected components by relative glyph height, baseline and
spacing, then adds a halo relative to measured glyph height. Ambiguous lines,
aligned fragments, clipped glyphs and insufficient margin return `UNKNOWN`
without invoking OCR. Original pixels are cropped; missing letters are never
reconstructed. Proposed bounds and crop pixel hash are recorded together with
implementation, input and OCR asset hashes.

Freeze inputs, methods and implementation before comparison. Compare methods on
the same native frames; do not select a method per frame or union accepted words.
Record integer native PTS, rational timebase, source identity, frame hash and
acquisition epoch in the companion evidence ledger. Separate acquisition windows
remain separate; an earlier readable word does not identify internal Round End.

## Development diagnostic result

A fixed comparison used 139 existing Native frames and 165 frames from 55 new,
content-blind, bounded development intervals. The latter are exposed development
data, not independent qualification data. One out-of-duration scheduled point was
excluded before decoding. The predeclared primary method used grayscale OCR;
white210 OCR was a separate secondary method.

| Method | Existing 139 | New 165 |
| --- | ---: | ---: |
| Configured crop, grayscale | 14 | 0 |
| Structured crop, grayscale (primary) | 21 | 4 |
| Structured crop, white210 OCR | 23 | 1 |

Counts are accepted exact-vocabulary observations at confidence >=0.90, not event
counts, complete-display GT, precision or recall. Existing Native observations
were reproduced exactly before comparison. A human-supported Result display
previously unreadable in all three retained frames became readable in all three.
Two formerly accepted frames were rejected by the fragment guard. The default
method remains available; the new method is an offline option, not a replacement.

The primary method proposed 45/139 existing regions and 4/165 new regions. Of the
45 existing proposals, 21 yielded accepted words and 24 remained OCR-unresolved.
Other frames include absent, animated and occluded displays; unreviewed frames
must not be called false negatives. One new readable observation failed frozen
HUD geometry and remains an uncertain raw observation. New repeated word frames
must not be counted as multiple physical events.

## Limits and next evidence

A proposed box does not prove that all glyphs of an animated word are visible.
Internal occlusion, generic background shapes, lower-contrast text, locale, HUD
scale and different layouts remain unqualified. White210 preprocessing regressed
on the new intervals and was not selected. Geometry consistency is not semantic
HUD ground truth. Optional human review must remain prediction-exposed development
review, separate from existing GT and independent qualification.

Keep last Active, score-change bracket, partial Result, first fully visible
Result and next-round witnesses separate. Exact visible-word and boundary labels
require corresponding evidence; unreadable or unreviewed cases remain UNKNOWN.
No Formal End or Self Death events, qualification evidence or production profile
are created by this diagnostic.
