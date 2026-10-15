# S-01: Snapshot field transport verification

## Decision

**B — safe global transport implemented and measured; acceptance remains incomplete.**

This change demonstrates A (observation retention) and B (legitimate global fact export), not C (a new PASS from the fixed 17). No new identity, owned-event, map or reader candidate is introduced. Adopted baseline remains 23/55/4; no experimental result is automatically adopted.

Start main: `7e480c2f2f7f49aea73e1541d065d78881d2f11c`. Dedicated review branch: `codex/s01-snapshot-field-transport`, based directly on that main. Production source is byte-identical to the separately tested working branch at `46462336427149764beb8e1fdd94c554e075616e`; its private investigation commits are not published. PR #42 remains untouched.

## Before / After by fixed assertion

Use identical saved source observations and existing native round windows. Before means the unchanged aggregate >=0.65 admission predicate; After means the additional independent field admission. This is a diagnostic projection, not two independent recognizer runs or a complete temporal application replay. No target expected value is passed into production. Time selectors only choose the offline windows.

| Assertion | Local observations | Snapshot before → after | Snapshot-derived facts after | Trace snapshots after | Canonical status |
| --- | ---: | --- | ---: | ---: | --- |
| GT-R1-SNAP-0415 | 4 | 0 → 4 | 12 | 4 | FAIL → FAIL |
| GT-R1-SNAP-585 | 6 | 0 → 6 | 18 | 6 | FAIL → FAIL |
| GT-R1-SNAP-595 | 11 | 0 → 10 | 23 | 10 | FAIL → FAIL |
| GT-R1-SNAP-733 | 7 | 0 → 7 | 17 | 7 | FAIL → FAIL |
| GT-R1-SNAP-734 | 7 | 0 → 7 | 18 | 7 | FAIL → FAIL |
| GT-R1-SNAP-7425 | 5 | 0 → 5 | 15 | 5 | FAIL → FAIL |
| GT-R1-SNAP-7438 | 3 | 0 → 3 | 7 | 3 | FAIL → FAIL |
| GT-R1-SNAP-7440 | 3 | 0 → 3 | 8 | 3 | FAIL → FAIL |
| GT-R1-SNAP-7445 | 2 | 0 → 2 | 6 | 2 | FAIL → FAIL |
| GT-R2-SNAP-11145 | 5 | 0 → 5 | 15 | 5 | FAIL → FAIL |
| GT-R2-SNAP-143 | 6 | 0 → 6 | 6 | 6 | FAIL → FAIL |
| GT-R2-SNAP-1475 | 2 | 0 → 2 | 2 | 2 | FAIL → FAIL |
| GT-R2-SNAP-1476 | 4 | 0 → 4 | 7 | 4 | FAIL → FAIL |
| GT-R2-SNAP-1477 | 2 | 0 → 2 | 4 | 2 | FAIL → FAIL |
| GT-R2-SNAP-149 | 2 | 0 → 2 | 6 | 2 | FAIL → FAIL |
| GT-R2-SNAP-151 | 11 | 0 → 11 | 33 | 11 | FAIL → FAIL |
| GT-R1-SNAP-0415-DERIVED-zone_id | 4 | 0 → 4 | 12 | 4 | FAIL → FAIL |

Do not sum overlapping target windows: the derived 4.15 target shares the same source frames as its parent. Across all windows there are **75 unique Snapshot PTS and 186 retained field supports**: ally score 56, enemy score 73, timer 57. All 186 supports reach facts and trace at the original PTS without confidence inflation. All newly admitted player-owned fields remain null/unknown; owned promotions = 0. No canonical PASS gain is attributed to this projection.

One local observation has no field at the accepted value threshold and remains absent; absence is not repaired. The table's extra snapshots represent distinct observed PTS, not fabricated duplicate frames. Confidence distribution per field and exact machine-readable counts are in [the aggregate report](../e2e_reports/match_001/s01_snapshot_field_transport.json).

## Current source-backed validation

A single completed canonical full on the current production code uses freshly checked, code/profile-bound component admission. Historical qualification was not re-signed. Native lifecycle has two starts, one end and two packages. The decoder, source, profile, code and terminal artifact hashes remain bound in private run metadata; all five terminal output digests were rechecked. Pack assertions and evaluator semantics are unchanged. The dataset manifest pack digest was synchronized only for eight earlier UTF-8 helper edits; 115 other pack files were byte-identical to the old completed-run state. The integrity guard itself is unchanged.

| Metric | Adopted baseline | Historical candidate | Fresh current full |
| --- | ---: | ---: | ---: |
| PASS | 23 | 28 | 28 |
| FAIL | 55 | 50 | 50 |
| NE | 4 | 4 | 4 |
| Negative violations | 0 | 0 | 0 |
| Round start / end | 0 / 0 | 2 / 1 | 2 / 1 |
| Native packages | 1 partial | 2 | 2 |
| Snapshots | baseline not re-counted here | 720 | 5335 |

All 82 current statuses match the historical candidate; no old candidate PASS regressed. All 20 negative assertions PASS, including content-jump spanning and no R2 end. The five improvements versus adopted baseline are lifecycle work already present in main, not S-01 snapshot accuracy gains: `GT-R1-ROUND-START`, `GT-R2-ROUND-START`, `event_count_constraints-000`, `event_count_constraints-002`, `event_count_constraints-004`.

Full analyzer exit 0, raw status complete, schema valid; evaluator/runner exit 1 reflects the remaining 50 semantic FAIL assertions. It is not an execution crash or a green full test. Original failure messages are preserved; 99 messages refer to 50 failing assertions, not 99 failed assertions.

R1 package [2.502669, 81.752669] has 3054 snapshots; R2 [110.986003, 171.019336] has 2281. The qualified preparation episode extension uses actual overlapping contiguous observations, never GT IDs; unknown fragments remain unassigned. R2 player timeline completeness remains 0 despite additional global snapshots. Fresh geometry is 1/6614 while effective geometry is 6614/6614; neither threshold nor retained policy changes.

Current frozen sampled: baseline 7 PASS / 12 FAIL / 11 NE; candidate 15 / 4 / 11 NE (30 points). Primary-state counts are identical; four remaining failures are unknown numeric fields. These 30-point metrics are separate from canonical 82. No new independent holdout is claimed: component admission rechecks existing frozen training/holdout/negative cohorts; all source exposure remains recorded.

## Negative controls and compatibility

The focused tests cover explicit unknown identity with valid globals, unrelated weak readers, spectator/remote poisoned player values, below-floor value proof, geometry without value proof, missing legacy confidence, NaN/Inf/out-of-range/bool/string support, current value changes, duplicate source rows, continuity breaks and native round membership. Global-only snapshots cannot widen map/spatial merges or package completeness. Existing aggregate gate, thresholds, actor, ownership and lifecycle contracts remain unchanged.

26 focused tests PASS (38.09 s), including the new diagnostic projection and JSON round-trip. Existing full regression on the same production code: 3765 PASS / 5 SKIP in 2586.30 s; actual process exit 0, including Qt shutdown regression. Five preexisting platform/fixture skips are not new skips. Ruff PASS; mypy 133 source files PASS. Dataset validation: 38 cases PASS; manifest-runner tests: 33 PASS. Linux/Windows CI, >=75% coverage, packaged smoke and stronger SQLite/checkpoint acceptance for this dedicated PR are pending and must be inspected before final acceptance.

## Reproducible low-cost replay

Keep raw observations and selectors private. Targets JSON has a `targets` list of `assertion_id`, `target_sec`, `tolerance_sec`; these are offline selectors. Additional expected values are discarded before calling production functions.

```bash
python -m scripts.diagnostics.replay_snapshot_gate \
  --raw /private/completed-run/raw_processing.json \
  --raw-sha256 <verified-terminal-sha256> \
  --targets /private/s01-targets.json \
  --output outputs/s01/replay.json
```

Existing output paths are refused. Input and production/adapter hashes are rechecked after execution. No new recognizer, lifecycle event or canonical verdict is generated. Source/profile/decoder/sampler qualification belongs to the original immutable raw run and must be checked separately; this tool never claims to renew it. The output contains source observations and must remain private. The public report contains aggregate metrics and assertion IDs, without GT definitions or source images.

Current-raw transport replay: **58.27 s**, peak process RSS **196.18 MiB**, private JSON **649408 bytes**. Historical same-input transport replay: 44.62 s (different load/system conditions, not a reliable speedup comparison). Full current run: **37848.92 s (10 h 30 m 49 s)**, 6614 main frames, 0.17475 main frames/s. Full peak RSS was not measured by the common runner; do not substitute replay memory for full memory. Geometry dominates at 11811.97 s; spectator 7126.82 s; numeric OCR 7014.73 s. Timings can be nested, so their percentages must not be added as exclusive totals. Full was launched before S-01's new request after unit, targeted, fixed sampled and current qualification checks; no full rerun was started for this diagnostic-only change.

## Remaining blockers / next producer

The fixed 17 retain all unproved player-state/ownership, death, map and spectator predicates. No global transport-only PASS gain is predicted. Next producer work should establish independently qualified current-frame identity/state and self-death subject evidence, with negative controls. Remote-state controls reviewed earlier are not discriminative enough for safe admission. Keep their output unknown rather than fitting another local template. R1 end's roughly 3 ms window miss is a separate semantic timing issue; no GT backdating is introduced.

Current provenance carries original run/profile/code hashes and original timer-reader provenance. Richer per-fact arbitrary image provenance is not implemented; do not claim an extended schema. S-01 remains B until the explicitly pending acceptance gates are verified. Main must not be merged automatically.
