# Source-preserved timer display contract

## Problem and targets

The timer reader previously returned source text but the analyzer reduced it to seconds. HUD v2 had no legal display field, native snapshots did not preserve it, and the trace adapter's display lookup could never receive it. This is a producer/contract defect, separate from timer recognition accuracy.

Targets are `GT-R1-SNAP-0415`, `GT-R1-SNAP-7438`, `GT-R1-SNAP-7445`, and `GT-R2-SNAP-11145`. Fixing their display transport alone does not satisfy package, state, ownership, score or other predicates. No canonical PASS gain is claimed.

## Contract and safety

For an accepted string timer result with nonempty reader sources, the analyzer preserves the source display (whitespace trimmed) as optional `values.round_time_remaining_display` and `round_time_remaining_display_provenance`. Provenance records reader name, source names, original confidence and cross-check status. The observation's current PTS associates the evidence with its frame. Both model and schema validation enforce display format, numeric/display agreement and the existing reader acceptance policy. Numeric-only results, missing sources and rejected/unparseable strings do not produce display evidence.

Native snapshots retain display only with reader confidence and the reserved current accepted-value confidence `round_timer_value` both at least 0.90. Generic geometry/ROI confidence cannot authorize it. Existing snapshot admission, identity and ownership requirements remain. Display changes and disappearance participate in snapshot deduplication so that spelling changes such as `01:05` versus `1:05` are not lost despite equal seconds. The trace adapter requires exact agreement between native display/provenance and the HUD observation at the same PTS; it emits `game_timer_display` and its source provenance. It never reconstructs text from seconds or carries a previous frame's text forward.

Production HUD and native snapshot schemas gain optional fields; required fields and schema version remain unchanged. Legacy artifacts without the fields still validate and numeric-only output retains its old shape. Consumers of new display fields need the updated schemas alongside the shared production code. The external validation pack, GT and assertion definitions are unchanged. Windows execution is not claimed verified.

## Verification

- Reader→HUD→native package→trace test preserves both `01:05` and `1:05`, original confidence/source names and exact PTS.
- Numeric-only input cannot produce display; rejected and missing readings cannot inherit old text.
- Malformed display, numeric disagreement, missing/weak provenance and native/source mismatch fail closed.
- Cross-checked low-confidence input and generic/missing accepted-value confidence cannot authorize native display.
- Related unit, integration and trace tests: **73 passed in 32.97 seconds**. Ruff passes; mypy passes for 98 source files.

A real replay of every native PTS in 70.4–70.6 seconds, plus three genuine calibration frames, used **the already rejected profile16 solely for transport diagnostics**. Eleven live observations preserve the reader's `0:33`, numeric 33 seconds and `tesseract_digits` source; one native snapshot and its trace snapshot retain that text and identical confidence 0.96916542 at PTS 70.402669. That source image was manually inspected and visibly shows `0:33`. No diagnostic labels were supplied to production. Source video, terminal archive and profile fingerprints were verified before and after processing. This is neither new numeric holdout qualification nor evidence that profile16 is safe: its three previously found wrong timers remain disqualifying, and profile13/default is not replaced.

The first source replay verified native transport; a second diagnostic version added trace export and verified the entire path. Final runtime is **41.488 seconds**, eleven selected frames, with no previous comparable full transport diagnostic. Artifacts and hashes are in [timer display diagnostics](../e2e_reports/match_001/timer_display_contract_diagnostics.json).

## Current limits

Canonical previous result remains **23 PASS / 55 FAIL / 4 NE**; current full result and delta are unmeasured. No new full E2E was executed because the three genuine round-boundary acceptance gates remain unmet. Preceding lifecycle targeted 0/5/2 and sampled 7/12/11 were run before this display change and are not represented as its new E2E validation.

The remaining upstream problem is accepted timer/live/end/continuity input from an adoptable profile. This change supplies the missing transport contract without adding an OCR candidate, relaxing a threshold, fabricating a timer or declaring any of the four target assertions resolved.

## Archived full compatibility check

The current builder, owned schemas and trace adapter were also exercised against all archived native inputs from adoptable profile13 and rejected profile16. Native packages, complete traces, every one of the 82 assertion outcome objects, and failure sets were identical to their original outputs. Source video and terminal raw/trace/evaluation hashes were verified before and after each reconstruction; the profile13 assertion definition hash also matches its run metadata. Legacy absence of display fields therefore preserves these actual archived outputs; display strings were never inferred from numeric values.

| Archived input | Observations | Offline wall time | PASS Previous / Current / Delta | FAIL Previous / Current / Delta | NE Previous / Current / Delta |
| --- | ---: | ---: | --- | --- | --- |
| Adoptable profile13 | 4634 | 37.824 s | 23 / 23 / 0 | 55 / 55 / 0 | 4 / 4 / 0 |
| Rejected profile16 | 4661 | 43.489 s | 23 / 23 / 0 | 55 / 55 / 0 | 4 / 4 / 0 |

These are different archived datasets, so their runtimes are not a candidate speed comparison; previous comparable runtime and delta remain null. Neither check decodes video or reruns recognition/lifecycle detection, and neither supplies new display-field safety evidence. The 20 negative assertions stay PASS on unchanged traces, but both traces contain zero temporal features; discontinuity protection of new behavior is still unproven. Profile16 stays rejected and Windows runtime is unverified. [Terminal report hashes and code/schema fingerprints](../e2e_reports/match_001/legacy_contract_compatibility.json) make the scope reproducible.
