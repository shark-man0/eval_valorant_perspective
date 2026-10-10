# Native source endpoint contract

## Problem / root cause / target

Explicit native lifecycle input previously required an observed frame at/before the requested start and strictly after the requested end. That correctly protects interior-window completeness but prevents requesting source-origin context for a video whose first PTS is nonzero, and prevents decoding the physical tail. The standard sampled runner is unchanged; this is a prerequisite for connecting qualified native lifecycle evidence through an entire source.

Targets: `GT-R1-ROUND-START`, `GT-R1-ROUND-END`, `GT-R2-ROUND-START`, related count/order assertions and package scope. No actual assertion is claimed repaired by input support alone.

HEAD: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.

## Change / contract

The shared Python `VideoService.native_window` accepts an explicit `end_sec=None` to request EOF. FFprobe and FFmpeg run to actual EOF; neither duration metadata nor a guessed last timestamp limits the frame list. Every decoded showinfo tick must match every selected probe tick, in order, before anything reaches the consumer. A truncated probe suffix cannot authorize a matching decode prefix.

`start_sec=0` explicitly requests the nonnegative source origin. A nonzero first native timestamp is preserved, with no zero-time frame fabricated or rebase applied. Negative-origin sources are currently rejected before decode rather than silently omitting their leading frames. Other numeric starts retain the existing left coverage requirement. A numeric end at the last frame still fails interior coverage; EOF must be explicit. At least two frames, strictly increasing exact ticks, one time base, source SHA256 checks and lossless pixel bindings remain required.

Bounded interior behavior, FPS, sampling, recognizers, qualification rules, assertion semantics, GT and safety thresholds are unchanged. Every decode invocation owns a new epoch; this change does not authorize joining separate windows across discontinuity. Decoder changes invalidate existing code-bound qualification through the existing fingerprint mechanism; historical reports were not resigned.

Example, for a suitably sized source:

```python
with video_service.native_window(
    video_path, start_sec=0, end_sec=None,
    source_video_sha256=verified_video_sha256,
) as native_frames:
    # Original PTS and verified pixels; no lifecycle authorization from decoding alone.
    ...
```

This API still buffers PNGs and frame descriptors until verification. It is **not incremental streaming** and does not install an automatic full-E2E provider. Decoding a large source entirely remains expensive in disk space and CPU. No full native decode or parallel full E2E was launched.

## Tests

22native decoder tests pass in15.05seconds with real FFmpeg/ffprobe and a small generated MPEG4 video. The source has a nonzero origin and variable native frame intervals. New coverage checks origin-prefix, entire source toEOF, suffix toEOF, exact finalPTS, temporary cleanup, truncated probe tail rejection, explicit-versus-numericEOF and rejection of negative origin without decode. Existing asset/source mutation and interior completeness tests remain green.

64native system/scene/lifecycle/merge tests also passed in66.18seconds after the endpoint implementation, before the final additional negative-origin guard. The final22-test decoder run covers that guard. Ruff passes `src tests scripts/e2e`; mypy passes116sourcefiles.

## Real source evidence

[The endpoint diagnostic](../e2e_reports/match_001/native_source_endpoint_validation.json) decodes the explicit0–0.15second prefix of the current video. It yields7frames, firsttick553at1/15360 (0.03600260416666667seconds), and all7decoded pixel hashes match the archived continuous-prefix diagnostic. Temporary assets are removed and source/profile-code terminal bindings are checked. Runtime13.607672seconds includes verification/decode, not recognition or E2E.

This measurement was recorded before the final negative-origin-only rejection guard. Its original fingerprint remains historical and has not been replaced to imply a fresh measurement. Actual source EOF was not decoded; EOF coverage is established on the generated variable-interval source, not the 171-second match video. The existing prefix frames are exposed development data, not independent holdout. No recognizer, qualified scene/UI proof, boundary or package was produced by this diagnostic.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Nonzero-firstPTS source requested with start0 | Rejected | Supported | Input contract fixed |
| Explicit native EOF | Unsupported | Supported | Input contract added |
| Actual source-origin decoded pixel matches | Unmeasured | 7 / 7 | New verification |
| Qualified actual scene/UI references adopted | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 archived | Unmeasured | Unmeasured |
| Canonical negative / discontinuity failures | 0 / 0 archived | Unmeasured | Unmeasured |

No targeted/sampled/full canonical run is claimed. A synthetic decoder test is not round lifecycle acceptance. All82archived assertion records remain unchanged.

## Remaining blockers / next work

R1 still has unqualified source/foreground continuity and positive UI-disappearance evidence. Existing original timer display transport was verified by code inspection; killfeed/death/spectator attributes still require actual source-backed readers and cannot be repaired by populating adapter aliases. No missing field was filled from expected values.

Automatic native processing still needs bounded resource use and persistent analyzer/scene/lifecycle state in a single decoder epoch, with terminal verification before releasing results. EOF support addresses one prerequisite, not that whole pipeline. Windows native decoder/OpenCV/file handling execution remains unverified. The full goal and conditional30PASS milestone remain incomplete.
