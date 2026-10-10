# Lossless native PNG prediction

## Problem / hypothesis / target

Whole native PNG buffering does not fit the current disk estimate. Stronger deflate compression saved only9.4%and raw-XOR/zlib increased storage26%; neither is adopted as the capacity solution. FFmpeg PNG spatial prediction is a separate reversible encoder option. Test it before introducing a different cache or splitting source epochs.

Targets remain real-source lifecycle, R1start/end, R2start and native package/count/order contracts. This storage work alone does not qualify any boundary. HEAD `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.

## Fixed codec evidence

[The benchmark](../e2e_reports/match_001/native_png_prediction_benchmark.json) reuses exactly the previous fixed eight-frame source cohort (indices0/25/50/75/100/125/150/179). Six documented encoder predictors run atcompression1in fixed forward/reverse order, one process at a time. All96encoded outputs reconstruct identical source BGRSHA256. Original source/report/script hashes are checked at completion. No GT, recognizer, frame skip, resize, random sampling, reference or qualification enters scoring.

| Predictor | Eight-frame bytes | Delta versus none | Mean encode seconds | Runtime delta |
| --- | ---: | ---: | ---: | ---: |
| none | 16963415 | 0% | 2.296651 | 0% |
| sub | 15639159 | −7.81% | 2.257482 | −1.71% |
| up | 13852926 | −18.34% | 2.107087 | −8.25% |
| avg | 16754324 | −1.23% | 2.449724 | +6.67% |
| paeth | 13731535 | −19.05% | 2.449314 | +6.65% |
| mixed | 13791982 | −18.70% | 3.045388 | +32.60% |

Choose `up` as the explicit available alternative: it improves both observed bytes and encode time. `paeth` and`mixed` do not offer that combination. This is a codec-cohort measurement, not all-source performance or recognition accuracy.

## Change / contract

Shared `VideoService.native_window` and `decode_native_window` now accept `png_prediction="up"`. The default is explicitly`"none"`, preserving the previously tested native encoding method. Other values fail before source access. Existing interior/origin/EOF coverage, source hashing, native integerPTS, passthroughFPS, dimensions, lossless pixels and terminal verification remain unchanged. No sampler/reader/threshold/policy/GT/assertion changes.

```python
with video_service.native_window(
    video_path, start_sec=0, end_sec=None,
    source_video_sha256=verified_video_sha256, png_prediction="up",
) as frames:
    ...
```

This example describes the option, not an invitation to run an unbounded large decode. The current native API still has no enforced total PNG storage budget or automatic whole-source provider. It is not incremental state processing. Each decode has a separate source epoch; comparing pixels across two decodes does not authorize joining their histories. Existing code-bound qualification fingerprints change through normal decoder/service hashing; historical reports are not resigned.

## Actual source decode verification

[The source test](../e2e_reports/match_001/native_png_prediction_source_validation.json) decodes the actual video's0–0.15second prefix twice. Seven frames in each decode have exactly identical source pixels, native ticks and time bases. Epochs remain separate, hashes are checked and temporary files are removed. No recognition or boundary evaluation occurs.

| Metric | Previous encoding none | Optional encoding up | Delta |
| --- | ---: | ---: | ---: |
| Native prefix frames | 7 | 7 | 0 |
| PNG bytes | 18501751 | 14926335 | −3575416 (−19.32%) |
| Source-verified decode wall seconds | 13.909540 | 13.412292 | −0.497247 |
| Pixel / PTS / time-base mismatches | — | 0 | No loss |

The wall-time difference is one serial none→up comparison and includes SHA/probe/decode/verification. It is indicative only; do not claim it proves an E2E speed improvement. Balanced repeated codec timing is the preceding eight-frame benchmark.

## Capacity decision

Extrapolating the eight-frame`up`mean to10259source frames estimates17.76GB, still above the previously observed17.26GBfree. These are estimates, not all-source allocation measurements. Therefore the option is useful but **does not solve whole-source capacity**. Keep default encoding and do not launch a full native decode without enforced resource bounds. The next producer must cap actual written bytes, reject incomplete output and preserve one epoch and complete source/state continuity; sampling smaller inputs or concatenating decoder windows would not satisfy it.

## Tests

91native decoder/system/scene/lifecycle/receiver tests pass in83.13seconds. New tests compare all source pixels/ticks/time bases between none/up on a generated nonzero-origin variable-interval video, and reject invalid prediction settings before source access. Existing corruption, source mutation, truncated probe, stale qualification and native event replay checks pass. Ruff passes`src tests scripts/e2e`and the benchmark script; mypy passes116sourcefiles. Windows FFmpeg/OpenCV execution remains unverified; unsupported encoder options fail closed.

Replay the codec benchmark to a new output:

```bash
python3 scripts/diagnostics/audit_native_png_storage.py \
  --source-report e2e_reports/match_001/r1_continuous_source.json \
  --indices 0 25 50 75 100 125 150 179 \
  --predictors none sub up avg paeth mixed --output /tmp/native-png-prediction-new.json
```

## Canonical Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| PASS / FAIL / NE | 23 / 55 / 4 archived | Unmeasured | Unmeasured |
| Actual scene/UI qualifications adopted | 0 | 0 | 0 |
| Actual qualified boundaries added | 0 | 0 | 0 |
| Default encoding / full sampler | Existing | Preserved | 0 |
| Negative / discontinuity failures | 0 / 0 archived | Unmeasured | Unmeasured |

No new targeted/sampled/full canonical E2E ran: actual R1source/foreground continuity and positive UI-disappearance qualification remain incomplete. All82archived assertion entries are unchanged. No30PASSclaim or goal completion follows from lossless codec support.
