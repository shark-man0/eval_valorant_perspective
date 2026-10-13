# Native UI measurements remain separate from qualified evidence

## Problem and fixed targets

`GT-R1-ROUND-START` and `GT-R2-ROUND-START`, their event counts and ordering
require source phase/timer evidence to reach the native lifecycle entrance.
`observe_frames` already returns current UI measurements, but the public native
measurement API discarded them. The development runner instead reconstructed
phase evidence from a diagnostic sink. Reuse the existing producer measurements;
do not introduce another recognizer or infer missing evidence.

## Contract change

`RealHudAnalyzer.observe_native_system_frames(..., include_ui_measurements=True)`
adds `system_measurements` to each source-bound native row:

```json
{
  "scope": "unqualified_current_frame",
  "qualification_required": true,
  "source_video_sha256": "source SHA256",
  "source_epoch": "decoder epoch",
  "source_pts_ticks": 63017,
  "source_time_base": "1/15360",
  "source_pts_sec": 4.102669270833333,
  "source_pixel_sha256": "pixel SHA256",
  "input_fingerprint": "input fingerprint",
  "native_ui": {
    "phase_scan_valid": true,
    "phase_present": false,
    "phase_confidence": 0.0,
    "phase_absence_matched": false,
    "confidence": 0.0,
    "round_result_matched": false,
    "round_result_confidence": 0.0,
    "content_jump": false,
    "discontinuity": false
  }
}
```

The example timestamp illustrates an observed source frame; no timestamp or
expected value is injected into runtime. Measurements come from the same
buffered analyzer pass as the returned observations. Current scan/presence,
explicit absence-template match, result-template match and source-break flags
remain distinct. Missing scan coverage, invalid boolean/confidence types,
nonfinite confidence and extraneous proof fields withhold the entire packet.
No failed scan becomes negative absence.

The option defaults to false and requires an actual boolean. Default output
shape stays unchanged. Opt-in is included in the input fingerprint. Returned
measurement dictionaries are independent copies, and source/profile terminal
checks remain in effect. The calibration prefix remains geometry-only and
never acquires a UI measurement or observation row.

`system_evidence` remains empty. Existing qualified admission rejects these
rows until actual qualification/proof is supplied through the existing qualified
producer. No formal lifecycle events or player-owned facts are emitted by this
measurement entrance. Strict mode, sampler, thresholds, acceptance policies,
HUD schema, trace schema and assertions are unchanged. This does not qualify
static templates or authorize caller-supplied evidence.

## Source replay and Previous / Current / Delta

Reuse all162 previously verified native rasters and their original integer PTS,
time base, decoder epoch, pixel/encoded hashes and source hash. Obtain a fresh
native startup frame for geometry-only initialization. No new suffix selection,
frame skipping, GT input or diagnostic sink. Windows remain independently reset
development cases, not a whole-source lifecycle or fresh blind holdout.

All162observations match the previous run exactly. Returned measurements also
match the previous diagnostic-derived phase/break evidence. Start candidates
retain every transient display and the same confidence, boundary and confirmation:

| Window | Boundary sec | Confirmation sec | Confidence |
| --- | ---: | ---: | ---: |
| R1 development | 4.102669 | 4.202669 | 0.954193 |
| R2 development | 111.419336 | 111.486003 | 0.931478 |

| Same input release/development metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Processed frames | 162 | 162 | 0 |
| Valid phase scans | 162 | 162 | 0 |
| Accepted timers | 133 | 133 | 0 |
| Development start candidates | 2 | 2 | 0 |
| Candidates in active/menu/spectator controls | 0 | 0 | 0 |
| Formal events from this entrance | 0 | 0 | 0 |
| Player-owned observations | 0 | 0 | 0 |

Total replay runtime424.829→302.354seconds, delta−122.476seconds. Totals are
not comparable for a speed claim: the current run reuses verified suffix
rasters, whereas the previous run decoded them. Timed analyzer portions are
284.656→275.604seconds, delta−9.052seconds (−3.18%); diagnostic sink overhead
and single-run variability also differ. No controlled performance gain claimed.

## Tests

51native transport/prefix tests and252lifecycle/package regressions PASS.
Ruff PASS; mypy PASS on128source files. Tests cover default compatibility,
source binding and copied measurements, opt-in fingerprint, coverage/type/error
rejection, terminal image mutation, no event builder calls, unchanged owned-field
projection and rejection by qualified evidence admission. Test-fixture readings
are synthetic and are not counted as real qualification support.

Full regression not repeated for this optional transport change; prior
2707PASS/6SKIPpredates it. No canonical full E2E: reader/UI qualification and
release gates remain incomplete. Canonical82status entries retain the historical
23PASS/55FAIL/4NE, not a current full result. Windows runtime not tested.

## Remaining blocker and next task

The producer-to-native current measurement contract now exists without the
ignored diagnostic callback reconstruction. Complete independent joint
phase/timer/UI qualification using honest control labels and physical split
provenance. Existing reviewed source cases cannot be called fresh holdout.
The source-native result reference still fails exact semantic training gates;
qualified end/rearm and R1/R2 whole-stream packages remain unproven. No package
or assertion is promoted simply because a start candidate can be reproduced.

Machine-readable comparison, terminal hashes and replay scope:
[native_ui_measurement_transport.json](../e2e_reports/match_001/native_ui_measurement_transport.json).
