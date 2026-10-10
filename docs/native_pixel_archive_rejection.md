# Rejected native pixel archive prototype

## Problem / hypothesis / target

Full-source native PNG buffering lacks a capacity guarantee on this Pi. Splitting decoder windows resets geometry/phase/scene/lifecycle and creates different epochs. Investigate a lossless internal cache that keeps every original pixel and PTS while exploiting adjacent-frame redundancy. Targets remain R1start/end, R2start, count/order constraints and native package scope. No numeric/OCR/recognizer candidate is introduced.

HEAD: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.

Hypothesis: fixed16-frame key images with XOR deltas and zlib level1would reduce total native storage enough to support one epoch. This hypothesis failed on the actual R1window.

## Implementation and evidence contract

[The diagnostic prototype](../scripts/diagnostics/pixel_archive_prototype.py) stores verified native frames and keeps original integerPTS, time base, source epoch/videoSHA256and pixelSHA256. Codec key images do not reset lifecycle. Each read verifies compressed dependency hashes and decoded pixel hashes, including reads served from the one-image cache. Returned arrays are copies. Whole-file terminal verification catches unused/trailing corruption. Explicit capacity overflow or any failed append poisons the buffer so it cannot publish a truncated prefix.

The prototype exposes typed `NativeSourceFrame` subclasses accepted by the existing shared reader and native global observation transport. That compatibility does not qualify a lifecycle proof. No archive JSON loader, recognized-result cache, reference, GT value or owned player evidence is introduced.

## Actual native-frame validation

[The result](../e2e_reports/match_001/native_pixel_archive_validation.json) uses all180already exposed native3–6s frames. Source videoSHA256, encodedPNG/pixel hashes and terminal input/code/report bindings are verified. Every source pixel, tick, time base and epoch is retained across two complete reading passes. Temporary cache data is removed. No new video decode, recognizer, geometry/lifecycle evaluation or canonical E2E occurs.

| Metric | Original PNGs | Prototype | Delta |
| --- | ---: | ---: | ---: |
| Stored bytes | 377191642 | 475393177 | +98201535 (+26.03%) |
| Source frames represented | 180 | 180 | 0 |
| Pixel / PTS mismatches | — | 0 / 0 across two passes | No loss |
| Cache construction seconds | Unmeasured comparable baseline | 86.336216 | Not comparable |
| Two reading passes seconds | Unmeasured comparable baseline | 125.249851 | Not comparable |

Total diagnostic time222.038127seconds includes input verification and cleanup. The previous PNG codec benchmark and adjacent-image measurement have different workloads, so their timings are not treated as a direct speed baseline. Storage can be compared directly for this exact180-frame set. No all-video size/speed claim follows.

## Decision / production change

Reject the raw-XOR/zlib cache as a storage solution. Correct reconstruction and passing contracts cannot compensate for a26%larger representation. Do not install it as a full-source provider or tune its codec interval against this exposed window.

The initial production prototype was removed and moved to diagnostic scope. Its temporary addition to the lifecycle code fingerprint was removed together with it. No production cache setting, recognition behavior, sampler, safety threshold, GT, assertion or adopted qualification is changed in the final worktree by this experiment. The result retains its original historical code fingerprint and script hash; neither was rewritten after diagnostic isolation/import formatting. The current diagnostic can replay the same method with new fingerprints, but is not claimed to have rerun the180-frame benchmark after that move.

## Tests

Final54tests pass in15.71seconds:14prototype contracts,22native decoder tests and18native system input tests. Coverage includes key boundaries/backward reads, source-byte equality, caller array mutation, cached ancestor corruption, trailing bytes, source epoch/hash/timebase/order changes, failed append/capacity poisoning and shared reader/transport compatibility. Positive fixtures are synthetic and do not grant real qualification.

Ruff passes `src tests scripts/e2e` plus both new diagnostic modules. Mypy passes116productionfiles after prototype removal. Windows execution remains unverified.

Replay requires existing source assets and a new report:

```bash
PYTHONPATH=.:src python3 scripts/diagnostics/validate_native_pixel_archive.py \
  --video ValorantData/videos/Valorant_09-25-2026_0-37-29-379.mp4 \
  --source-report e2e_reports/match_001/r1_continuous_source.json \
  --max-bytes 500000000 --output /tmp/native-pixel-archive-new.json
```

## Previous / Current / Delta

| Canonical metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| PASS / FAIL / NE | 23 / 55 / 4 archived | Unmeasured | Unmeasured |
| Production delta cache adopted | 0 | 0 | 0 |
| Actual source/UI qualification adopted | 0 | 0 | 0 |
| Negative / discontinuity failures | 0 / 0 archived | Unmeasured | Unmeasured |

All82assertion records remain unchanged. No full E2E was run because there is no qualified actual-boundary candidate. The full goal and conditional30PASS milestone remain incomplete.

## Remaining blocker / next safe action

The principal R1acceptance blocker is still independent source/foreground and positive UI qualification; the existing-source provenance question is pending. Independently, automatic one-epoch full-source resource handling is incomplete.

Local FFmpeg encoder help establishes that PNG `pred` defaults to`none`; compression level and spatial prediction are distinct settings. The previous PNG benchmark changed compression level only. A concrete next storage hypothesis is a fixed-cohort test of lossless spatial prediction, checking exact pixels, bytes and wall time with the existing encoder. Do not claim capacity/recognition gains before measurement. The next decoder/provider must enforce an explicit storage budget and preserve terminal verification; a smaller cohort or state concatenation cannot stand in for whole-source behavior.
