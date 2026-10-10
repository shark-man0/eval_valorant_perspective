# Native PNG storage budget

## Problem / target

Optional lossless PNG up prediction improves the measured codec cohort, but does not guarantee that the full source fits disk. A whole-source native provider must fail without publishing partial evidence when capacity is exhausted. Decoder windows cannot be concatenated to bypass capacity: they create different source epochs and reset analyzer/scene/lifecycle context.

Targets remain the real-source lifecycle→native event/package→trace path, R1start/end, R2start and count/order constraints. Input resource enforcement alone does not satisfy actual-boundary acceptance. HEAD `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.

## Change / contract

Shared `VideoService.native_window` and `decode_native_window` accept optional `max_png_bytes`. A positive integer enables one FFmpeg encoder writing lossless PNG records to a binary pipe. PNG chunks are read in bounded pieces and the aggregate encoded byte limit is checked **before** each file write. Successful files and an in-progress partial file together stay within the configured PNG limit. Invalid budgets fail before source access. The limit covers PNG files, not metadata/logs, so callers still need free-space margin.

No frame, observation, proof or boundary is exposed until decoder exit, exact native showinfo/probe tick equality, coverage, dimensions/pixel binding and source SHA256 checks pass. Budget overflow kills/reaps that decoder, removes the temporary directory and raises `VideoProbeError`; it never turns a decoded prefix into a successful interval. Malformed/truncated PNG records, missing frames, nonzero encoder exit or timeout likewise fail. A one-shot timeout protects blocking pipe reads, with pipe/process cleanup; no periodic PID/log/file-completion checks are used. Reading encoded frame bytes is necessary decoder transport, not status polling.

Each successful context retains one decoder epoch. Every source frame in the explicit interval/EOF remains represented, with original integerPTS/time base, passthroughFPS and unchanged pixels. Recognition/geometry/identity/ownership/discontinuity thresholds, sampler, GT and assertion semantics are unchanged. Decoder/service source changes participate in the existing qualification fingerprint; old reports are not resigned or automatically reused.

`max_png_bytes=None` retains the existing file-output decode route. Default PNG prediction remainsnone. Example for a caller with an explicit PNG allowance:

```python
with video_service.native_window(
    video_path, start_sec=0, end_sec=None,
    source_video_sha256=verified_video_sha256,
    png_prediction="up", max_png_bytes=png_storage_allowance,
) as frames:
    # Complete verified source only; overflow never enters this block.
    ...
```

The encoder transport is streamed, but the consumer still receives the complete verified sequence after decode. All successful PNGs remain buffered until context exit. This does not implement incremental recognizer state, solve every source's capacity needs or install an automatic full-E2E provider. It provides a strict failure contract for the full-source input prerequisite.

## Tests

101native decoder/system/scene/lifecycle/receiver tests pass in87.39seconds. New coverage includes exact pixel/PTS agreement between budgeted and ordinary decoding on a nonzero-origin variable-interval video, single epoch throughEOF, pre-write aggregate bounds, overflow withholding/temporary cleanup, invalid budget rejection, exact-byte limits, multiple/fragmented/truncated records, one encoder timeout/pipe cleanup and truncated-probe rejection in the budgeted route.

Ruff passes`src tests scripts/e2e`; mypy passes116sourcefiles. The timeout test was rerun successfully after a Ruff-only with-statement formatting correction. Windows pipe/FFmpeg/OpenCV execution remains unverified. No parallel full E2E or model-side status polling is introduced.

## Actual source verification

[The source check](../e2e_reports/match_001/native_png_budget_source_validation.json) runs the current video's explicit0–0.15second prefix withupencoding and20MBPNGallowance. It preserves all7previously decoded frames, original ticks/time bases and decoded pixel hashes; sumPNGbytes14926335. Temporary images are removed. A separate attempt with50bytes raises `native PNG storage budget exceeded` before the consumer block. Neither attempt runs recognition or supplies qualified lifecycle evidence. Source/report/code bindings are checked at completion.

| Metric | Previous ordinary up decode | Current budgeted up decode | Delta |
| --- | ---: | ---: | ---: |
| Native prefix frames | 7 | 7 | 0 |
| PNG bytes | 14926335 | 14926335 | 0 |
| Source pixel / PTS / time-base mismatches | — | 0 | No loss |
| Source-verified decode wall seconds | 13.412292 | 13.389124 | −0.023168 |
| Explicit pre-write aggregate PNG bound | Absent | 20000000bytes | Added |
| 50byteattempt publishes partial frames | Previously unmeasured | No | New rejection evidence |

The wall difference is one historical/current prefix comparison with different code fingerprints and includes SHA/probe/decode/validation; it is not a speed guarantee or an E2E benchmark. Capacity enforcement does not prove full-source completion. No full native source or canonical full E2E was run.

## Canonical Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| PASS / FAIL / NE | 23 / 55 / 4 archived | Unmeasured | Unmeasured |
| Actual scene/UI qualification adopted | 0 | 0 | 0 |
| Qualified actual boundaries added | 0 | 0 | 0 |
| Negative / discontinuity failures | 0 / 0 archived | Unmeasured | Unmeasured |

All82assertion rows remain unchanged. No inference about newly passing assertions is made from decoder success.

## Remaining blocker / next implementation

An automatic shared native lifecycle provider still needs to preflight current qualification/assets before any large decode, select an explicit storage allowance, consume this complete single-epoch sequence through the existing analyzer/scene/lifecycle once, and deliver only validated native boundaries to the ordinary processor. It must not silently fall back to sampled boundaries or a truncated input if resource/qualification checks fail.

Actual R1source/foreground and positive UI disappearance remain unqualified; source provenance remains pending. The native resource guard cannot answer that image-evidence question or authorize a false R2end. No acceptance-ready candidate exists, so targeted/sampled/full canonical E2E was not justified. The broader goal and conditional30PASS milestone remain incomplete.
