# Rejected End score-support restart experiment

The private attempt to retain an End proposal across missing score reads is **rejected**. It can confirm an isolated early OCR outlier using a later real score change, producing an incorrectly early boundary. No production recognizer, threshold, timestamp rule, ownership logic or qualification bundle changes. A public regression test preserves the existing conservative behavior.

## Development evidence and declared experiment

Use only the original development pool300–600 of source `06919642d69f68895ac123b505bfd7d3643dd28d903585008fcdc2b7f1b7e3fd`. Code remains `58117f2bfe84f072c37f0989846145d7fad7a3a29d807ba55d9be9a6136a4f68`, private profile `445f61d7440dee58c480253338b19df500c676c519e84810d1f7332c3ea798ee`. Earlier evaluated A/B/CLUTCH/WON cases are never new blind cases for this changed method.

Saved-row inspection of development354–362 and444–452 finds no numeric-clock End proposal. Source review explains why: the former changes from Spike icon to an inter-round clock, and the latter from Spike icon to a retained decimal25.28 display. The strict numeric timer correctly abstains on unsupported representations; missing numeric-before evidence must not be synthesized.

Before predictions, select another development-only context518–526, preserving all481 native frames,775,118,219 PNG bytes, actual decoder epoch/PTS and terminal source/image hashes. Current producer runtime130.7817 seconds. The numeric clock changes0:58→0:06 at522.6333333333333; accepted adjacent score3–2→4–2 at522.95. Current diagnostic End confirms at523.5333333333333, confidence0.9038290977478027. No independent temporal GT or formal End claim is made from this training case.

The frozen private prototype retains an already observed adjacent +1 score proposal when later OCR is unknown. Unknown resets consecutive score support; a fresh stable run is required. Source breaks, conflicts,0.90 confidence, the one-second deadline and first observed score-change timestamp remain. Any potential production adoption would require separate explicit qualification rather than enabling the policy by default. Prototype SHA256 `42e4cdace9c3798a2325052c78df3d1d059e8b3bc254b2ce3f809b6f4eb26d00` binds the tested implementation.

## Preliminary results did not prove safety

Seventeen synthetic tests pass: consecutive support restarts without counting missing frames; permanent/intermittent unknowns, weak evidence, initial-transition gaps, contradictions, source breaks, menu/phase and timeout remain rejected; original proposal confidence is not upgraded by later higher reads. These tests are not real source qualification.

Fresh actual production measurements of the four fixed negative windows contain76 frames, zero result matches and zero diagnostic Ends; runtime82.7677 seconds. Previously exposed fixed negatives are regression evidence, not independently certified temporal negatives. Explicit development geometry prefix is retained; it does not supply continuity or active Start.

Offline replay of immutable actual current reader outputs preserves the development numeric End at522.95. An explicitly synthetic copied-row stress with one missing post-transition score is recovered. Replay of the **already exposed** WON788–792.5 case also recovers a diagnostic pattern at788.6333333333333, confidence0.9150651693344116. That recovery is not independent evaluation or End qualification. No reader is rerun for these offline comparisons and real source observations remain unchanged.

The original fixed match_001 End still has timestamp74.48600260416667, outside unchanged GT by approximately3.003ms. The private prototype also lowers its confidence from0.9180924279198346 to0.9028293490409851 because it incorporates later accepted score confidences. Do not describe all provenance/confidence as unchanged or use this experiment to pass the known timing miss.

## Timing-safety counterexample: reject the prototype

A separate synthetic control models an isolated confident early score outlier at0.44, unknown score reads0.46–0.74, then the actual +1 change and result at0.76 or later. Neither tracker receives the synthetic truth as an input. The observed sequence is compatible with an early false read; later agreement cannot establish the original change time across the unknown interval.

Existing production tracker: no End. Private prototype: End0.44 at confidence0.95, **320ms before** the modeled actual change. The additional safety test fails, even though the earlier17 pass and selected real cases appear improved. This violates the required temporal safety. Do not retune the candidate on the newly opened evaluation cases or promote its diagnostic result.

The retained production guard now has an explicit regression `test_isolated_score_outlier_cannot_be_attested_by_later_change_after_unknown_gap`. Its fixture contains synthetic OCR evidence only; it asserts conservative abstention, active-round preservation and unchanged input rows. Related production End/caption tests: **55 PASS in0.92s**; focused Ruff PASS. No production change means no new full real-video run or repeated full regression is justified for this test/report addition.

## Held exposure and next work

The1530–1800 pool was opened only for source discovery after the private method freeze, fixed negatives and regressions. Coarse source images identify three new score-update episodes (10–7→10–8,10–8→10–9,10–9→10–10), excluding physical events previously exposed at1500/1800. Refined approximate source images were extracted. **No native held producer/recognizer evaluation is run**: the new timing counterexample rejects the method first. Preserve this exposure history; do not claim the pool remains wholly unseen or that unexecuted evaluations passed/failed.

A safer next direction is to investigate why current score readers lose complete support at the transition, without retrospectively joining unsupported score runs. Any reader improvement needs development-only source evidence and newly frozen independent cases; an uncertainty interval or different timestamp contract would also need a separately reviewed specification and qualification. Do not change the official GT, extend acceptance windows, fill unknown values, or simply move the old boundary.

Actual current Start-only admission remains unchanged and loadable with bundle `a1bebb223d6805f1da9ee4ee6dacd6da130001d6da451075e76e2186d16f9591`: timer/purchase_phase/ui_transition only. End/full lifecycle remain unqualified; no default bundle, formal End, Package/Trace release, full E2E or main merge follows from this experiment. The adopted experimental caption-family implementation is unaffected.

Machine-readable aggregate: `e2e_reports/match_001/end_score_restart_rejected.json`. Private prototype, raw rows, source frames, labels, profile and manifests remain ignored. The failed experiment and its hashes are retained rather than hidden or relabeled as successful qualification.
