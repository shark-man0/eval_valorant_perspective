# Whole-source qualified native lifecycle verification

## Problem and evidence

Window diagnostics cannot prove a single continuous start/end/next-start path.
Run the actual qualified source-assured native entrance once over all 10259
source frames, using the current six-component experimental admission bundle.
No GT, external system proofs, substituted times or player identity bypass
enters the detector. The bundle remains local and is not installed by default.

An initial 0–114 second PNG acquisition exhausted its explicit 8GiB budget
before recognition began. Preserve that failure; do not increase storage
without limit or skip frames. Reuse the existing bounded `native_replay` API
instead. It verifies full-source PTS and pixels on every decoder pass and
retains only a few raw images; recognition is one call across the physical
source origin through EOF. Two preflight launch failures (test-package import
path and unsupported service timeout argument) also occurred before decoding.

## Current observed behavior

| Native event | Boundary | Confirmation | Confidence | Actor |
| --- | ---: | ---: | ---: | --- |
| R1 start | 4.102669 | 4.202669 | 0.911719 | system |
| R1 end | 74.486003 | 75.369336 | 0.919552 | system |
| R2 start | 111.419336 | 111.486003 | 0.900047 | system |

Starts use source-observed purchase-phase disappearance and stable subsequent
clock evidence, preserving the literal transient displays. The end uses clock
decrease, score update/stability and the later qualified result caption. Its
boundary is the observed score update; confirmation does not replace that
time. R2 end is absent throughout the remaining source. No duplicate boundary
is produced. Every event retains source SHA, exact PTS, raster hash, code/profile/
qualification fingerprints and continuity segment through package and trace.

Identical adjacent decoded rasters at 81.786003 and 81.836003 create two source
breaks. The completed R1 history is not carried through them. R2 starts from
fresh observed preparation in continuity segment 2. This proves source-local
R1 and R2 detection, not uninterrupted R1→R2 rearm across a source break.

Two schema-valid packages are created:

| Package | Observation window | Snapshots | Events |
| --- | --- | ---: | ---: |
| R1 | 3.602669–81.769336 | 56 | 107 |
| R2 | 110.986003–171.019336 | 133 | 62 |

Event counts include derived global numeric facts. Package endpoints are
association windows, not replacements for start/end event timestamps. The R2
upper endpoint is the metadata duration sentinel, not an observed round end.
Initial context before 3.602669 and inter-round context after the source breaks
are not proven round-owned. In particular, the earlier R2 buy menu remains
outside its current package. These association gaps remain open work.

The system transport deliberately contains zero player-owned facts. Primary
states retain current producer context (8676 unknown, 680 live, 579 buy menu,
324 spectator), without attributing HP/weapon/death/shot to an unknown player.

## Evaluation and Previous / Current / Delta

Apply the unchanged canonical evaluator to this native-only trace. Its 82
outcomes are 27 PASS / 51 FAIL / 4 NE. This is **not the standard full E2E**:
native frame density, experimental profile and global-only observation transport
differ from the adopted 23 PASS / 55 FAIL / 4 NE run. Keep that baseline intact.

| Comparison | Adopted standard full | Experimental native trace | Arithmetic delta |
| --- | ---: | ---: | ---: |
| PASS | 23 | 27 | +4 |
| FAIL | 55 | 51 | -4 |
| NE | 4 | 4 | 0 |
| Starts | 0 | 2 | +2 |
| Ends | 0 | 1 | +1 |
| Packages | 1 partial | 2 | +1 |
| Negative assertion failures | 0 | 0 | 0 |

Five assertions change FAIL→PASS: `GT-R1-ROUND-START`, `GT-R2-ROUND-START`,
`event_count_constraints-000`, `event_count_constraints-002` and
`event_count_constraints-004`. `GT-R1-SNAP-705` changes PASS→FAIL because this
native-only trace has no snapshot in its required window for the expected live
state and smoke flag. Its cause must be checked in the full application merge;
do not inject a snapshot or weaken identity to conceal the diagnostic loss.

`GT-R1-ROUND-END` stays FAIL: 74.486003 is approximately 0.003003 seconds outside
the unchanged acceptance window ending at 74.483. Ordering assertions remain
NE. A detected end-count PASS does not imply a point-window PASS. All 20
negative assertions pass on this trace, including no R2 end and no event span
across content jumps. This does not prove detection of missing death/shot
features or constitute full application negative-regression certification.

## Runtime, tests and remaining work

Producer time: 17704.993 seconds (4.918 hours). Measured decode/producer/check
stage: 19703.275 seconds (5.473 hours); package/trace transport follows that
measurement. No parallel full E2E ran. Hash verification succeeds.

Previously verified current correction: 108 related unit tests, Ruff and mypy
PASS. Full regression after integration with remote branch/main is recorded
separately. Windows dirty-worktree execution is not yet verified.

Next targets: full application integration under current evidence, preservation
and association of unknown pre-round context, independent temporal qualification,
sampled regression, then eligible standard full E2E. Do not change GT/windows,
backdate the end, claim all 29 package failures solved, or install this bundle
as a default based on one exposed result episode.

Machine-readable full 82-outcome diagnostic:
`e2e_reports/match_001/qualified_whole_source_lifecycle.json`.
Local source outputs:
`outputs/recognition-investigation/qualified-whole-source-lifecycle-20261013/`.

## Integrated regression checkpoint

Remote branch changes including latest main and Match aggregation integrate
without conflict. Recognition fingerprint remains unchanged. At integrated
HEAD `de7c9d8014f74026e862b1a21611ab2b5d2ab426`, full regression is **3224 PASS /
6 SKIP in 2157.26 seconds**; Ruff PASS; mypy PASS on 131 source files. Skips
cover the separately configured real-video fixture, local Tesseract, native
Windows paths and unavailable PowerShell. They are not Windows verification.
The separate source-native whole-video run above remains the real-image
lifecycle evidence. Linux/Windows GitHub CI will run after push.
