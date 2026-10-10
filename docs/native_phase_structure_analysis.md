# Native purchase-panel structure analysis

## Problem

The semantic text recognizer proves purchase-phase presence only. Its low-contrast nonmatches cannot establish disappearance. The R1 start path needs independently qualified current UI evidence, in addition to scene continuity. Target: `GT-R1-ROUND-START` and subsequent lifecycle count/ordering predicates.

## Evidence and independent image evidence

HEAD: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`. The source video is unchanged, SHA256 `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.

[Measurements](../e2e_reports/match_001/native_phase_structure.json) use all 30 previously exposed native R1 frames, verified encoded/pixel hashes, integer PTS step 256 and time base 1/15360. No timer value, expected event time or validation pack is read. Three non-overlapping image structures were selected offline: upper panel edge `[745,133,1178,143]`, lower edge `[745,276,1178,286]`, purchase button `[928,248,1005,275]`. They exclude the timer and central phase text. These are development regions, not qualified references.

Sobel gradient and grayscale contrast are descriptive statistics. There is no detection threshold, semantic decision or runtime authorization.

| Structure statistic | 4.086003 s | 4.102669 s | Delta |
| --- | ---: | ---: | ---: |
| Upper edge mean absolute vertical gradient | 64.265 | 1.136 | -63.129 |
| Lower edge mean absolute vertical gradient | 60.287 | 0.545 | -59.742 |
| Purchase button mean absolute horizontal gradient | 67.444 | 0.129 | -67.315 |
| Purchase button grayscale std | 36.927 | 0.468 | -36.459 |

The upper, lower and button structures change together at tick 63017 (4.102669270833333 s), corroborating the earlier full-image review of panel disappearance. Upper-edge standard deviation remains 4.543; different structures must not be reduced to a single flatness test. Weak structure gradients persist through the remaining native window. The first transient timer/view-model change is one native frame later, tick 63273 (4.1193359375 s), as recorded in the separate UI-localization investigation. This establishes temporal ordering of observed image changes, not the semantic reason for either change.

## Competing hypotheses and continuity decision

Normal phase-panel removal is consistent with disappearance of three separate UI structures before the foreground switch. An opaque overlay, image replacement or scene-preserving edit can also remove those structures. The panel measurements do not rule these out and do not prove scene continuity. Keep phase absence unknown in production until a complete source/UI contract passes independently reviewed controls.

## Contract change

None. `measure_structures` always returns unknown presence/absence, `absence_checked=false` and `runtime_transition_authorized=false`. It reads no references, labels, profiles or GT. No system event or owned player fact is released. Production thresholds, semantic matcher and full sampler remain unchanged.

## Tests

Six new tests cover blank/black/white obscuration withholding, independent local measurements and rejection of overlapping, repeated, missing or invalid structures. Combined with native UI/foreground tests: 17 passed in 0.98 seconds. Ruff's import-order issue in the new test was corrected; the final Ruff check passed for `src tests scripts/e2e` and this diagnostic. Mypy passed for all 112 source files. `git diff --check` passed.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Independently measured non-text UI structures | 0 | 3 | +3 |
| Native frames measured for these structures | 0 | 30 | +30 |
| Qualified phase-absence producers | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | Unmeasured | Unmeasured |

Runtime: 3.718996 seconds for saved-image measurements, not comparable to a native decode or E2E. No targeted/sampled/full E2E was run because no qualified candidate was produced. All 82 archived assertions remain unchanged.

## Remaining blocker

Independent controls must distinguish full/partial panel obscuration and scene replacement from source-supported panel removal. Distributed scene continuity remains unresolved for R1's view-model change. The measurements narrow the timeline but cannot be promoted directly into `global_ui_transition`. Next derive a current-image background-reveal contract from these separate structures with independent controls, and join it only to qualified native source continuity. Windows execution is unverified.
