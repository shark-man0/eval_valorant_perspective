# Qualified Strict lifecycle with bounded raw replay

## Problem

Whole-source PNG storage exceeded the explicit 8GiB ceiling before recognition.
The existing raw replay decoder already verifies complete source PTS, raster
hashes and terminal source integrity with bounded memory, but the application
collector rejected it solely because Strict Mode was selected. A direct native
analyzer experiment could use replay; the shared Strict application/CLI could
not. This blocked the source→native→application→package→trace path on the Pi.

## Change

Allow explicitly selected `NativeLifecycleOptions(storage_mode="replay")` in
Strict Mode. Reuse the existing `VideoService.native_replay`; do not introduce
another decoder, sampling method or lifecycle state machine. Default storage
stays PNG. The legacy positive PNG budget argument remains required for CLI/API
compatibility; replay uses its separate raw buffer ceiling instead.

Qualification selection is still determined by **boundary mode and source
contract**, never by storage. Strict requires current qualification, production
readers and either qualified scene binding or the explicit SHA-bound unedited
input contract. It still returns `NativeLifecycleAnalysis`, not a practical
candidate result. Practical remains a distinct explicit mode.

Complete native frame coverage, source geometry/epoch/cadence, source rows,
pixel hashes and terminal qualification/input integrity are verified as before.
Missing qualification, altered coverage/pixels and terminal decoder failures
remain errors; none trigger sampled fallback or candidate promotion.

## Common orchestration

The same Python runner on Windows/Linux accepts:

```text
--native-storage replay --native-replay-buffer 67108864
```

Use these with existing `--mode full`, positive `--native-png-budget`, a qualified
HUD profile and exactly one of `--unedited-input-contract` or
`--scene-reference-profile`. There is no implicit qualification or example
profile installation. The current experimental bundles are stale and must not
be used without fresh source verification.

Both CLI layers validate/forward options. Run configuration fingerprints bind
the storage selection and raw buffer allowance; raw runtime metadata reports
them. `targeted`/`sampled`, unbound source, invalid storage and nonpositive buffer
cannot silently enable collection. The ordinary full command without native
options keeps its existing sampler and behavior.

## Tests and Previous / Current / Delta

| Behavior | Before | Current |
| --- | --- | --- |
| Explicit qualified Strict replay | Rejected as practical-only storage | Existing qualified provider, whole source, terminal checks |
| Missing paired qualification | Rejected | Rejected before decode |
| Coverage/pixel/terminal mismatch | Rejected | Rejected in PNG and replay |
| Default PNG command | Existing behavior | Existing behavior |
| Formal event semantics | Qualified Strict boundaries | Qualified Strict boundaries |

Related provider/assured/practical/orchestration tests: **142 PASS in 112.63s**.
Decoder/merge/cross-platform tests: **58 PASS / 1 host-Windows SKIP in 26.89s**.
The decoder tests exercise real synthetic FFmpeg sources, including repeated
reads, source mutation and cached pixel mutation. They are not real gameplay
qualification. Ruff PASS; mypy PASS on 131 source files. No thresholds, GT,
assertions, ownership, identity or default full sampling changed.

## Remaining gates

Current recognizer fingerprint:
`96c79de983a298b1f849c742c9653728c527481d929e2991b6e6f918dfe95da5`.
The unchanged loader actually rejects the old bundle as
`Invalid or mismatched global lifecycle qualification`.

Fresh current-code source qualification and real qualified application merge
are pending, as are current-code full regression, sampled/full acceptance and
Windows CI. Do not claim current source accuracy from the earlier native whole
run or re-sign its old counts. No new long real-video run was launched in this
change. Adopted canonical E2E stays **23 PASS / 55 FAIL / 4 NE**.

Machine-readable report: `e2e_reports/match_001/strict_native_replay.json`.
