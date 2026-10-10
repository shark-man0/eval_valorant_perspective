# Native foreground control comparison

## Problem

R1's first transient timer frame also changes hand/knife presentation. Matching background regions cannot establish that only timer UI changed. Whole non-UI NCC cannot by itself distinguish a view-model animation from a background-preserving content jump. Target remains `GT-R1-ROUND-START`; no GT value enters production.

## Evidence

Starting main: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.
Source SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.

[Foreground measurements](../e2e_reports/match_001/native_foreground_controls.json) cover all 126 native frames in the explicit development window 0.2–2.3 seconds. Integer ticks have time base 1/15360 and step 256. Five local contact sheets show every foreground frame; timer/phase are excluded from these sheets and crop selection. Source pixels, reference assets, code and report bindings are checked. This is exposed development evidence, not independent holdout.

Three fixed post-pose crops are `[940,750,1120,850]`, `[1080,600,1190,740]`, `[1440,930,1600,1050]`. The strongest minimum similarity to the R1 first-transient pose occurs at tick 31017 (2.0193359375 seconds): NCCs 0.931517 / 0.842172 / 0.912939. Minimum 0.842172 fails 0.90. No qualified pose match is claimed. These same coordinates include wall in the pre-pose reference; pre-pose and consecutive pair scores cannot establish semantic object correspondence.

## Competing hypotheses

1. A normal inspect-like view-model transition occurs independently of the phase/timer transition.
2. A background-preserving edit switches view-model presentation.

Visual similarity makes the first hypothesis worth testing, but does not exclude the second. The control itself has no independently reviewed no-edit ground truth.

## Independent image evidence

[A second native decode](../e2e_reports/match_001/native_foreground_control_pair.json) covers all five frames in 2.0–2.07 seconds. Pixels and encoded PNG hashes agree with the earlier 126-frame decode. Full native image review at ticks 30761 and 31017 shows idle-like knife presentation switching to open-hand inspection-like presentation.

The same excluded timer/phase masks and six background regions used for R1 give:

| Diagnostic | R1 first transient | Exposed control switch |
| --- | ---: | ---: |
| Whole non-UI NCC | 0.345489 | 0.524857 |
| Changed non-UI pixels (maximum BGR difference ≥8) | 389399 | 501848 |
| Minimum of six background NCCs | 0.995074 | 0.833593 |

The control has five background regions above 0.90 and one below. Camera motion, changed content or contamination remain possible; these fixed unwarped regions do not qualify continuous camera motion. Changed-pixel counts are descriptive, not acceptance thresholds.

## Continuity decision

Do not authorize continuity or declare a cut from whole non-UI NCC alone. R1 remains unresolved between a view-model transition and a background-preserving jump. A pure timer-only description is unsupported. The control does not qualify a normal-animation whitelist, a new mask or a relaxed threshold.

## Contract change

None. Production retains fail-closed qualification. Background support, foreground presentation, phase presence/absence and temporal timer evidence must remain separate. Unknown phase glyph matches cannot become phase-absence evidence. This diagnostic cannot authorize system events or player-owned facts.

## Tests

Five foreground comparison tests cover input bounds, distinct crops, unavailable texture and descriptive-only output. Six native UI localization tests cover independent regions and excluded timer/phase measurements. All 11 passed in 0.85 seconds. Ruff passed for `src tests scripts/e2e` and the two diagnostic modules; mypy passed for all 112 source files. Source-profile/runtime qualification is still absent; no full E2E candidate was created.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Native foreground development frames measured | 0 | 126 | +126 |
| Native control-pair frames measured | 0 | 5 | +5 |
| Qualified continuity/normal-animation controls | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | Unmeasured | Unmeasured |

Foreground window runtime: 79.053355 seconds. Control-pair runtime: 32.233225 seconds. They cover different work and are not a speed comparison. Canonical round events, packages, negative failures and discontinuity violations have no new measurements. All 82 archived assertion entries remain unchanged.

## Remaining blocker

Source-continuity and current-frame phase-absence qualification are still missing. Native decoding and common descriptive scene APIs exist, but there is no independently qualified paired scene/UI producer. Next investigate distributed camera evidence separately from view-model animation and a qualified phase-disappearance contract before lifecycle integration. Do not prioritize R2 thresholds or result-banner thresholds to bypass R1 uncertainty. Windows execution remains unverified.
