# Positive chromatic Spike correction and observed clock-type order

The private clock-type method now recognizes the missing WON Spike without lowering NCC0.90 or the digit competitor margin0.04. All72 fixed source-labelled development frames receive the correct type/rejection and decimal literal. This is development feasibility, not End detection or formal qualification. No production code, profile or event path changes.

## Actual source diagnosis

Compare the first source-labelled LOST and WON Spike crops and their masks, using the same fixed120×70 region. The original mask requires R≥200 as well as R−max(B,G)≥100. In the WON source there are1584 pixels meeting the positive chromatic contrast condition, but zero also meet R≥200. Their maximum R is179. The entire ROI's maximum R is239 because it also contains nonred HUD strokes; that overall maximum must not be mistaken for red-icon brightness. The resulting old mask is blank, and NCC to all three training references is0. This is an extraction failure, not a missing icon or a template-placement failure.

The frozen new method removes only the absolute R≥200 white-brightness condition, retaining positive red contrast≥100. Re-extract the same three fixed training masks at354.0/354.25/354.5 seconds. Keep Gaussian3×3, full fixed-position mask matching and NCC0.90. No reference search, threshold sweep or new source frame is used for fitting. Decimal glyph rectangle/white200 extraction, DD.DD grammar, ten-class competition, NCC0.90/margin0.04 and conflict rejection remain identical. The method returns only kind/literal/confidence/reason, never countdown seconds, identity or owned facts.

A numerical description in the frozen plan mistakenly says red maximum191. Preserve that immutable plan and add a separate description erratum: measured red maximum among positive-chromatic pixels is179, overall ROI maximum239. Code, source labels, masks and results are not altered by this correction; neither value meets the old red200 condition.

## Paired development results

Source SHA256 `06919642d69f68895ac123b505bfd7d3643dd28d903585008fcdc2b7f1b7e3fd`; only the original354–362,444–452 and518–526 second windows are used. Production recognizer remains `414f9d9d…`, base profile `ca8aa2a0…`. Exact private method/reference/label hashes separately bind this experiment.

| Fixed source-labelled grid | Previous calibrated mask | Positive chromatic mask |
| --- | --- | --- |
| Spike,11 frames | 10 correct / 1 unknown | 11 correct |
| Decimal,23 frames | 23 correct | 23 correct |
| Numeric countdown,38 frames | 38 correct rejections | 38 correct rejections |
| Wrong type/literal on grid | 0 | 0 |

Three of the Spike frames are the actual reference-training frames. These72 exposed development frames are not independent holdout; the23 decimal frames are one physical event, and Spike frames span two physical events.

All1,443 static development calls reproduce the72 grid predictions exactly. LOST retains191 positive Spike frames. WON changes from0 to11 positive Spike frames, retains432 decimal predictions and returns unknown on38 other frames. Every predicted decimal literal is25.28. Numeric-window481 frames remain outside the supported two types. Outside the labelled grid, predictions are not assumed correct merely because they are accepted. Grid/full elapsed1.615/29.434 seconds excludes acquisition and is not a native lifecycle runtime benchmark.

Twelve malformed/synthetic controls still reject. Additional background challenges use12 fixed off-HUD positions on each of three physical development frames. Assistant source-only review labels all36 crops before prediction; all36 reject. These background crops are not natural timer-location absence,36 independent events or formal End-negative evidence. No new held image is opened.

## Temporal constraint before End integration

Actual saved components in WON show the last positive Spike at444.166667 seconds, first accepted updated ally score3 at444.183333 seconds, and first positive decimal at444.200000 seconds. Native cadence is256 ticks at1/15360. Thus the observed score update lies between the two positively recognized clock types; decimal becomes readable one frame after score.

The current numeric End tracker requires its accepted clock change before the adjacent accepted score update. These measurements do not satisfy that contract. Do not forge a numeric countdown, move the decimal timestamp back, inject a transition into the existing tracker or claim successful End. A distinct type-transition protocol would need independently reviewed timing semantics, positive source witnesses on both sides, the actual first observed score-update timestamp, later confirmation, strict score adjacency/stability, current unknown handling and the unchanged one-second association limit. Source epoch/cadence and every break must remain binding. This protocol is not implemented or admitted here.

Next, fix and test that separate temporal contract using existing development inputs before any distinct unviewed physical event is enrolled. Independent positive/negative source review and complete current-code native replay remain necessary. Existing numeric timer admission cannot qualify clock types automatically. Complete original-source R1 End timing, lifecycle continuity and full R2 membership are still unresolved.

This report-only checkpoint does not rerun full regression or Full E2E. Private images, masks, labels and full logs remain outside Git. Keep Issue #16 open and PR #42 draft. The previous CI network query was rejected by automatic approval review because of its usage limit; no push or current Linux/Windows CI success is claimed.
