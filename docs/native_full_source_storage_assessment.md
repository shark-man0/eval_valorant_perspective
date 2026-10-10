# Native full-source storage assessment

## Problem / target

The native origin/EOF API and qualified boundary receiver exist, but they do not yet form an automatic whole-source provider. Arbitrarily dividing decoder windows is unsafe: each call creates a new source epoch and analyzer/scene/lifecycle state. First assess whether the existing single-epoch PNG buffer can cover this source without that split.

Target: real-source lifecycle through native packages/trace, especially `GT-R1-ROUND-START`, `GT-R1-ROUND-END`, `GT-R2-ROUND-START` and related count/order constraints. HEAD `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.

## Evidence / hypothesis

The180existing native3–6s PNGs total377191642bytes, average2095509.12bytes and maximum2761251bytes. Free workspace disk was17263181824bytes. Local ffprobe reports10259source frames at60/1fps. These counts do not establish all-source PNG size: gameplay content and compression vary.

A potential alternative to incremental state is stronger lossless PNG compression. [The fixed benchmark](../e2e_reports/match_001/native_png_storage_benchmark.json) uses source indices0/25/50/75/100/125/150/179, selected deterministically before encoding, from the exposed180-frame archive. There is no random sampling, GT input, recognition run or frame skipping in full E2E.

## Method

The shared diagnostic stages the eight existing PNGs and runs one FFmpeg process at a time. Compression levels1/6/9 run in fixed order1,6,9,9,6,1. Each run must output all eight images and their decoded BGR SHA256must match the source. Source/code/report bytes are checked before/after. All48encoded outputs preserve the original pixels. Encoded images are temporary and removed. The timings include the serial process and image decode/encode, excluding output verification; they are codec microbenchmarks, not E2E speed measurements.

The benchmark uses saved PNG inputs, rather than the MP4 decoder, and does not test native PTS. No parallelism, production codec setting, recognizer, sampler or policy is changed. Forward/reverse repetitions reduce order bias but do not establish general Pi performance or an all-source size guarantee.

## Previous / Current / Delta

Mean wall time over two runs; output bytes are identical within each level.

| Metric | Level1 baseline | Level6 | Delta6 | Level9 | Delta9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Eight-frame bytes | 16963415 | 15387393 | −9.29% | 15364444 | −9.43% |
| Encode wall seconds | 2.293922 | 3.303599 | +44.02% | 3.755647 | +63.72% |
| Original decoded pixels preserved | 8 / 8 per run | 8 / 8 | 0 mismatches | 8 / 8 | 0 mismatches |

Extrapolating the fixed cohort mean to10259frames yields21.75GBatlevel1,19.73GBatlevel6and19.70GBatlevel9 (decimalGB). These are **estimates**, not measured full-video storage. Even the strongest tested setting exceeds the observed17.26GBfree space. It would be unsafe to treat this small codec cohort as a resource guarantee or start an unbounded full native decode based on it.

| Canonical metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| PASS / FAIL / NE | 23 / 55 / 4 archived | Unmeasured | Unmeasured |
| Qualified real source/UI references adopted | 0 | 0 | 0 |
| New actual round boundaries | 0 | 0 | 0 |
| Negative / discontinuity failures | 0 / 0 archived | Unmeasured | Unmeasured |

## Decision / change

Reject stronger PNG compression as a sufficient fix for whole-source storage. Keep the existing production compression setting. Do not work around capacity by splitting decoder epochs and concatenating lifecycle state, dropping frames, resampling or weakening terminal validation. This is a resource feasibility conclusion, not a continuity or UI qualification.

The remaining architectural requirement is source processing with bounded image storage and persistent state within a single decoder epoch. Any such implementation must preserve exact original integerPTS/pixels, calibration/reader/scene/lifecycle context, discontinuity resets and terminal source/profile/code verification before public results. The current buffer API is not claimed to provide this. No provider, streaming implementation or alternate cache format is added by this diagnostic.

## Tests

Ruff passes `src tests scripts/e2e` and the new diagnostic. The six actual encoder executions verify coverage and source-pixel equality, plus terminal source/code/report immutability. No production code changes, additional unit tests, mypy rerun or canonical targeted/sampled/full run are involved. The previous22decoder tests,64relatedtests and116-filemypy results remain historical. Windows codec execution is unverified.

Reproduce to a new report:

```bash
python3 scripts/diagnostics/audit_native_png_storage.py \
  --source-report e2e_reports/match_001/r1_continuous_source.json \
  --indices 0 25 50 75 100 125 150 179 \
  --output /tmp/native-png-storage-new.json
```

## Remaining blockers

Whole-source resource handling is an independent incomplete pipeline task. The principal actual acceptance blocker remains qualified R1source/foreground continuity and positive UI disappearance. These images do not supply an independently reviewed normal-animation label; the existing-source provenance question remains unanswered. No result here qualifies a start/end or changes any of the82archived assertion states. The full goal and conditional30PASS milestone remain incomplete. Avoid another PNG-setting variant or an unnecessary full decode; the measured savings already fail the storage requirement.
