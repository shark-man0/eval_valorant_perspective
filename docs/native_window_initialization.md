# Explicit source initialization for native system windows

## Problem and target

Cold native windows at R1/R2start and three control contexts have only1accepted
anchor. Existing geometry policy correctly rejects them. A full application
starts from the source's initial image, where4anchors are accepted. Prepending
that image in a diagnostic reproduced candidates but also let it enter feature,
value and phase context. Targets remainGT-R1-ROUND-START,GT-R2-ROUND-STARTand
associated count/ordering constraints; no canonical PASS is claimed.

## Change

The common RealHudAnalyzer.observe_native_system_frames entrance now accepts
explicitcalibration_prefix:NativeSourceFrameandinput_contract_path:Path.
Both are optional; neither default full processing nor sampler changes. The
extra entrance is system-measurement-only and requires a configured v3profile,
matching explicit unedited source assurance and a verified earlier decoder-owned
image with the same source hash, timebase and dimensions. Missing assurance,
other video, future/bool/negativePTS, invalid epoch or changed bytes reject.
No source contract is inferred or automatically applied to another video.

Only the existing anchor detector and v3calibration validator see the prefix.
It never enters feature observation, value/OCR readers, phase temporal context,
roster comparisons, UI transition or event streams. No injected anchors or
synthetic confidence. The ordinary retained-geometry rule remains: only
insufficient_anchorsmay use the accepted earlier calibration; current geometry
contradictions, including letterboxing, cannot borrow it. Prefix anchor failure
rejects initialization. Fresh current geometry remains measured separately.

Current windows retain all contiguous decoder PTS/pixel identities and original
indices; no prefix observation is added, removed from a produced stream or
rebased. Packet projection excludes all player-owned values and world trust.
No event builder runs. The qualified event entrance is unchanged and requires
its independent qualification; this option cannot authorize formal events.

## Provenance and terminal checks

The input fingerprint binds prefix source/pixel/encoded hashes, PTS,timebase,
dimensions and assurance-file hash along with existing profile/code inputs.
Read the prefix again after processing and reject terminal pixel/file/assurance
changes before returning a packet. Calibration diagnostics separately retain
source time, age at window start, anchor scores and assurance provenance.
They do not call an old reference a fresh current-frame acceptance.

Source assurance excludes user edits, not recording loss. It provides no
continuity proof across the unprocessed prefix→window gap. Native window cadence,
source breaks, current ROI availability and reader/ownership policies remain.
Shared initialization reference must be declared in later provenance/split
review; it cannot count as a new independent UI event witness.

## API usage

Keep both decoder source owners alive while measuring. Supply a previously
verified source SHA and explicit matching user-assurance file.

```python
with service.native_window(
    video, start_sec=0, end_sec=0.08, source_video_sha256=source_sha256,
) as startup:
    with service.native_window(
        video, start_sec=window_start, end_sec=window_end,
        source_video_sha256=source_sha256,
    ) as frames:
        systems = analyzer.observe_native_system_frames(
            frames, native_step_ticks=native_step_ticks,
            calibration_prefix=startup[0],
            input_contract_path=input_contract_path,
        )
```

An uncalibratable startup image fails closed. These are measurement rows, not
Round events or qualification. Existing callers omitting the new arguments keep
the old callback keyword signature, output schema and behavior.

## Tests

113related testsPASS; full2707PASS/6SKIP, exit0,1918.35s. Previous2690PASS/6SKIP,
1865.89s: +17tests,+0SKIP,+52.46s/+2.81%; changed test count, not a speed claim.
RuffPASS,mypy128source filesPASS. Tests cover real source metadata rejection,
assurance/byte mutation, no value/phase reads from prefix, no formal events,
projection ownership, native gap rejection, insufficient prefix anchors,
current letterbox veto, fresh-versus-retained metrics and old override signature.
Synthetic test detector outputs do not constitute real qualification.

## Current source validation and Previous / Current / Delta

The actual public API reprocesses162native frames across the frozen5windows
with no injected readers, positions or qualifications. Every suffix PTS/pixel
hash matches the prior development replay. Profile assets are unchanged; code
fingerprint changes and older qualification is not re-signed.

| Metric | Previous startup-observation diagnostic | Current API | Delta |
| --- | ---: | ---: | ---: |
| Native window frames | 162 | 162 | 0 |
| Valid phase scans | 162 | 162 | 0 |
| Accepted timers | 133 | 133 | 0 |
| Start candidates | 2 | 2 | 0 |
| Candidates across3controls | 0 | 0 | 0 |
| Formal events | 0 | 0 | 0 |
| Projected owned observations | 0 | 0 | 0 |

R1candidate4.102669/confirms4.202669; R2candidate111.419336/confirms111.486003,
both exactly unchanged. The current162windowframes havefresh_geometry_success0,
effective_geometry_success162andretained_geometry_frames162. Prefix4anchor
acceptance is reported separately. No current fresh acceptance is invented.

Actual source run424.829sversus421.970s,+2.859s/+0.68%. Execution differs in
initialization/provenance work, so this is descriptive, not claimed faster.
No canonical full E2E is run: exposed development contexts are not independent
joint qualification and the acceptance gates are incomplete. Historical82status
records remain23PASS/55FAIL/4NE; Current full/Delta unavailable.

## Remaining blockers

Independently reviewed timer/UI qualification and correct negative scope remain
missing. This API does not complete R1end/R2rearm, full lifecycle continuity or
package/event adoption. The end timestamp/result semantics and fixed expected
score discrepancy remain unchanged. No boundary is promoted merely because its
candidate falls inside an assertion window. Windows execution and CI for current
uncommitted changes are unverified. Next use the common measurement entrance for
independent joint qualification rather than duplicating ignored callback code.

Source/code/artifact hashes and full comparisons:
[native_initialization_api.json](../e2e_reports/match_001/native_initialization_api.json).

## Current UI transport follow-up

The optional native entrance now supports `include_ui_measurements=True` to
retain existing same-pass source-bound UI measurements in an explicitly
unqualified namespace. It does not populate system_evidence or enable events.
See [contract and162frame replay](native_ui_measurement_transport.md).
