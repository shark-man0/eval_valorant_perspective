# Positive clock-type development feasibility

A private development prototype positively recognizes retained decimal text without converting it to countdown seconds. In the fixed72-frame source-labelled grid, the calibrated method reads all23 decimal displays correctly, identifies10/11 Spike images and rejects all38 countdown images as outside its two supported types. This is not End detection or qualification. The WON development episode has no accepted Spike anywhere in its481-frame window, so a positively evidenced Spike→decimal End path cannot yet be established.

## Source and fixed development scope

Source SHA256 `06919642d69f68895ac123b505bfd7d3643dd28d903585008fcdc2b7f1b7e3fd`. Use only existing354–362,444–452 and518–526 second development windows. The72-frame source-only grid and manual labels were saved before this clock-type experiment: each integer second through start+7, with offsets0,0.25,0.5. It contains11 Spike displays,23 decimal `25.28` displays and38 numeric countdowns. The decimal positives are one physical event, not23 independent events. All data are exposed development; no independent held images are opened.

Current production recognizer remains `414f9d9d…`, base profile `ca8aa2a0…`. The private method is separately identified by its exact source and template/label hashes. No production profile, admission, code or event-generation path changes.

## Two positively evidenced types

Spike uses three fixed actual source-labelled training images at354.0/354.25/354.5 seconds. Extract a binary positive-red mask (R≥200 and R−max(B,G)≥100), preserving the fixed120×70 crop at source x900:1020,y15:85. Compare Gaussian3×3 masks at NCC0.90 with no spatial search, resampling, threshold scan or unknown-as-Spike fallback. These are three physical frames from one development event, not independent events.

Decimal parsing requires exactly four full digits and one low decimal dot, consistent heights/top alignment, positive gaps and a dot between digits2/3. Every normalized digit competes against0–9 with the original binary glyph bank, Gaussian3×3 comparison, NCC0.90 and margin0.04. Return the literal DD.DD and type only; never interpret its numeric value as round-time seconds. Both type channels are measured; a positive conflict rejects.

The initial fixed-crop Otsu version fails all23 decimal positives because it segments the gray panel and surrounding HUD strokes along with characters. Its actual measurements remain immutable. Original training-source inspection shows digit foreground at local y20:45 and unrelated HUD strokes startingy57. The calibrated decimal path fixes a separate inner glyph rectangle x12:108,y12:53 (source x912:1008,y27:68) and white200 extraction. This is source-based development layout calibration, not evaluation-guided timing adjustment. Spike processing is unchanged. The new method and ROI are saved before its calls.

## Actual results

| Source-labelled grid | Initial | Calibrated |
| --- | --- | --- |
| Spike,11 frames | 10 correct / 1 unknown | 10 correct / 1 unknown |
| Decimal,23 frames from one event | 23 unknown | 23 correct / 0 unknown |
| Countdown,38 frames | 38 correct rejections | 38 correct rejections |
| Wrong type/literal on this grid | 0 | 0 |

Initial/calibrated grid runs take1.461/1.466 seconds. Replay the calibrated reader over all1,443 cached full source images, verifying every pixel hash and reproducing all72 fixed grid predictions exactly. It accepts191 Spike frames in LOST and432 decimal frames in WON; all432 literals are `25.28`. It accepts no Spike in WON and no noncountdown type in the numeric window. The remaining predictions are not all source-labelled and are not assumed correct. Full static calls take29.932 seconds excluding acquisition; this is not native lifecycle producer timing or a performance benchmark.

Twelve malformed/synthetic controls reject: black/white/red/gray fields, wrong dtype/channels/shape/empty ROI, removed dot, duplicated colon dot and removed first digit. They derive from one exposed decimal source and are not twelve independent natural negatives or End-negative events. Every prediction has only kind/literal/confidence/reason; none outputs timer seconds, player identity or ownership. Source-label, method, reference, manifest, profile and code checks pass at run boundaries. Private source-only images, masks, raw labels and full rows remain outside Git.

## Remaining implementation gates

This demonstrates a limited noncountdown observation primitive, not temporal evidence. Diagnose the missing WON Spike using its actual source images and mask geometry; do not rename unknown as Spike or remove positive recognition requirements. Source-labelled training must cover the relevant display variations, with separate alternate-type and absence controls. Decimal training validation currently contains only one literal/event and cannot prove broad DD.DD generalization.

A future explicit clock-type End path must preserve first observed score-update time, later result confirmation, the one-second association limit, same-source epoch/cadence and source-break rejection. It must not fill current unknown scores, borrow existing numeric timer qualification, inject events, backdate clocks or turn decimal values into countdowns. No such path is implemented or admitted in this checkpoint. Complete native replay and a prospectively fixed evaluation on distinct unviewed physical events remain necessary; current development events cannot serve as independent holdout.

Formal End qualification, original R1's3.003ms GT miss, full lifecycle and R2 ownership/membership remain unresolved. No full E2E or implementation regression rerun is claimed for this private prototype/report-only checkpoint. Keep Issue #16 open and PR #42 draft. The earlier network CI query was rejected by automatic approval review because of its usage limit, so this checkpoint is not pushed and no current Linux/Windows CI success is claimed.
