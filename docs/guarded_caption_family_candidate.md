# Guarded Round-result caption family: frozen candidate assessment

The old guarded profile only covers TEAM ACE. Add an **opt-in**, guarded complete-caption family for `round_end_template`; no default profile or qualification is installed. A private new-source profile trained on separately allocated development events covers LOST and WON. It improves complete LOST recognition on held event supports, but does **not** establish End qualification or the requested complete match_001 lifecycle. Issue #16 remains open.

## Implementation and configuration

`SemanticTextFamily` accepts 2–8 named complete `SemanticTextReference` models with equal image shapes and thresholds, each with a glyph-local contrast guard. It takes the maximum **whole-caption** score. It cannot assemble a caption from different variants' good glyph groups. Unknown remains unknown; matching cannot attest absence, authorize a transition, or establish player ownership.

The existing semantic `round_end_template` specification is the primary caption. An optional `variants` array contains 1–7 objects with exactly `label`, `template`, `mask`, `support_regions`, `training`, `contrast_guard`. Each label is nonempty, distinct and trimmed; `primary` is reserved. Each training entry contains exactly `template` and `frame_sha256`; the existing model verifies at least three distinct source hashes and training support at the fixed threshold. Each contrast guard has exactly `method: glyph_local_contrast_v1` and `template`. Variants inherit the primary ROI and threshold; overrides are rejected. Variants are prohibited for other signal roles/matchers. Any malformed variant disables the signal, including primary fallback. All variant assets participate in existing recursive profile fingerprinting.

Existing single-caption profiles retain their prior behavior. Global recognizer fingerprints change, so old qualification bundles must be rejected and actually revalidated. This change does not alter temporal predicates, the one-second End association horizon, thresholds, boundary timestamps, source continuity, strict mode, or ownership.

## Frozen experiment and exposure

The user confirmed the additional recording was unused and unedited, then explicitly authorized pre-splitting its previously unseen intervals. Source SHA256: `06919642d69f68895ac123b505bfd7d3643dd28d903585008fcdc2b7f1b7e3fd`.

| Allocation | Source seconds | Meaning |
| --- | --- | --- |
| Excluded prior baseline | 0–180 | Previously viewed failed old-method evaluation; never new blind holdout |
| Development | 300–600 | Geometry/caption training and controls |
| Held event candidates | 1200–1500 | Source-only discovery and labels after candidate freeze, before predictions |
| Negative candidates | 1800–2100 | Selected reviewed windows, not an all-negative recording interval |

Split plan SHA256 `ff449e2aca51edf9150800bdd0f290f4a3516b747beb1dd8793156e2b74daf91`; native training manifest SHA256 `2ce9774a46de7343de6bda42c9f2da17d8cbde05e942e6cdb83590aa3b0a54a1`.

Candidate code fingerprint `7897d6bcb9600c6541b48a26c94cd4e22bd9a3a692269366a0b3e2d5610e4dbc`; private candidate profile fingerprint `445f61d7440dee58c480253338b19df500c676c519e84810d1f7332c3ea798ee`. Freeze precedes held/negative viewing. No subsequent tuning. The original profile is preserved separately.

Development training uses native frames at 300–300.04 for four geometry anchors, 360–360.04 for LOST, and 450–450.04 for WON. Three physical parents per caption are correlated supports of one event, not three events. Result ROI [840,150,1080,250] includes the complete larger glyphs; foreground/support masks and guards are derived only from development images. Anchor thresholds and NCC remain 0.90. Six development controls reject result captions. The inherited timer/score readers are unchanged. Spike-icon-without-numeric-before-clock cases remain unsupported.

## Held results

Actual `observe_native_system_frames` processes all 488 native frames in two independent windows, each with a genuine development native frame used only as an explicit geometry prefix. Source contract, native cadence, decoder epochs and terminal raster/hash checks are retained. No epochs or lifecycle states are joined. Geometry prefix support is not a same-epoch active Start proof. Per-frame geometry outcome totals and producer elapsed/RSS were lost after an exporter error and remain **unmeasured**.

Assistant source labels on 11 selected native images were frozen before predictions. The user independently confirmed A's displayed 10–4 / 0:15 → 10–5 / 0:06 then complete LOST, and B's 10–5 / 1:03 → 10–6 / 0:05 then complete LOST. This confirms source sequence contents only, not exact End GT, all per-frame labels or recognizer approval.

| Held case | Native interval | Frames | Caption matched frames | Complete score pairs | Diagnostic End patterns |
| --- | --- | ---: | ---: | ---: | ---: |
| A | 1359.8–1365.5 | 343 | 44 | 264 | 0 |
| B | 1434.8–1437.2 | 145 | 51 | 141 | 1 |

Selected support comparisons: timer 10 correct / 1 unknown / 0 wrong; ally score 11 correct; enemy score 10 correct / 1 unknown / 0 wrong. Of seven complete LOST positive supports, six match and one complete animated caption remains unknown. Three selected non-complete controls reject. One ambiguous support is excluded from semantic comparison. These are two events, not 11 independent events. WON has development support only; held WON coverage is missing.

A starts a pending clock proposal at 1361.6833333333334 and expires it at 1362.7. The first semantic result match is 1364.7833333333333, over three seconds after the clock change and outside the unchanged one-second horizon. Saved-row inspection, without reader rerun, verifies this abstention; do not extend the horizon using this held failure.

B's **diagnostic**, unqualified pattern uses first accepted score change 1435.5833333333333, confirmation 1436.4166666666667 and confidence 0.9018939137458801. These are measured recognizer outputs, not source-approved exact boundary GT. No formal event, Package or Trace is released from either case; owned player facts remain zero.

An optional display-key exporter failure occurred after both producer calls. Immutable raw rows were already saved. Finalization validates every cached native image/identity and hashes, then compares source labels and replays diagnostic trackers only. It does not rerun recognition or discard failed/unknown cases. Raw-row SHA256: A `43d816b1f5aaae000701550266601daa4ce9922fe3c81fca563b8f1800c287a3`, B `485b0ff23abfd54b2eff528e9984450056caee9085d5d4c5f44270d49de891a2`.

## Negative candidates and original-source regression

Four predetermined windows (active 1800–1800.3, scoreboard 1830–1830.3, glow-active 1860–1860.3, spectator/Spike 1920–1920.3) contain 19 native frames each. Across 76 frames: zero semantic result matches, zero diagnostic End patterns, zero owned facts. Effective geometry is retained from the explicit development prefix; none establishes fresh current-frame anchors. Full temporal human GT is absent, so these observations are not a certified zero-FP rate. Runtime 72.736 seconds.

Fresh current-code calls on original fixed assets/splits reproduce phase 3 training / 8 held correct / 12 controls rejected; timer 25 correct / 7 unknown / 0 wrong, eight alternate-field controls rejected; score 36 correct / 18 unknown / 0 wrong fields and 54 negative field false positives zero; result 3 correct / 8 unknown / 0 wrong and three controls rejected. Original exposure is preserved; these are regressions, not new blind qualification.

Fresh native decoding of eight original fixed windows covers 369 frames in 166.250 seconds with terminal integrity checks. Start diagnostics and the known End 74.48600260416667 remain unchanged. The canonical End upper bound 74.483 remains missed by approximately 3.003 ms. No GT/timestamp rounding or baseline update is allowed. Old qualification bundles fail current-code fingerprint validation.

## Validation and remaining gates

17 new synthetic tests cover complete-caption matching, mixed-caption rejection, blank/wrong shape, unsafe definitions, opt-in parsing, fail-closed malformed variants and variant-only asset fingerprint invalidation. Related unit tests: 358 pass; dataset checks: 38 pass; Ruff passes; mypy passes on 131 files. Full local run: **3657 pass / 4 fail / 9 skip**, 425.27 seconds, coverage 86.3831%. The four existing spectator-icon failures remain explicit and outside this caption change. Exact new-commit CI is reported separately; earlier green jobs do not qualify this code.

Still required for formal End/full lifecycle: independently reviewed exact native temporal GT and negative windows, held WON coverage for the proposed family, independent validation of a method handling delayed captions and Spike-icon cases, current-source geometry/continuity assurance and one genuine uninterrupted active Start→End path, complete original R1/R2 Package/Trace membership and no false R2 End through EOF. Do not fabricate a current six-component bundle, infer source continuity across separate windows, or launch/claim full E2E from these bounded diagnostics. Private images, labels, profiles, contracts and exposure ledgers remain Git-ignored; tracked artifacts contain aggregates and hashes only.

## Bounded Start revalidation before concurrent main integration

The original immutable static/UI splits were rechecked against actual current-code measurements and source labels, including 9 training / 7 held-review / 90 negative UI supports. A private three-component Start-only audit, SHA256 `63eaa79b8a436ae0cddc6f3d1ca0f0de9a7f6f5c8f6aa61bde1142d796d438ab`, is accepted by the actual loader for code `7897d6bc…`. The prior audit is rejected. This is actual revalidation, not a fingerprint-only rewrite; historical exposure remains explicit.

Actual qualified native source entrance on 0–6 seconds, 358 frames: R1 Start 4.102669270833333, confidence 0.9117099378029602. The exact event/attributes reach one partial Package and Trace; zero End/snapshots/owned facts, completeness zero. Production elapsed 116.670 seconds, total 149.266 seconds, retained PNG bytes 607,990,858, peak process RSS 148,865,024 bytes. Canonical GT-R1-ROUND-START passes after production; no GT is supplied to production. The application fixed-frame HUD/visual integration also reproduces the event and passes the same targeted assertion. This does not prove a whole-source lifecycle.

A subsequent fetch found main advanced from `c11ec6d333957cccb270417bc95a8a57f433e6ad` to `edc3b684aadac25b076665dcbb55bda254d335f3`. Its merged decoder/visual UTF-8 and strict native replay changes affect the broad recognizer fingerprint. The experiments above remain the frozen pre-integration evidence. They must not be relabeled current-main qualification by editing fingerprints. Latest-main integration/revalidation follows separately. The report-only predecessor aa00e6a has three passing CI jobs and one Linux job aborting with exit 134 after 3646 passing tests; it is not an all-green result.
