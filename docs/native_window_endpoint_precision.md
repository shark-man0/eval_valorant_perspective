# Exact PTS endpoints in targeted source acquisition

Start main: `7e480c2f2f7f49aea73e1541d065d78881d2f11c`.
Branch: `codex/native-window-integer-pts`, independent of the Self Death reader
and other active recognition branches. No qualification report is transferred
to this changed decoder.

## Problem and evidence

A source-bound S-01 negative-control acquisition was correctly withheld because
FFprobe and FFmpeg disagreed about its first frame. The source contains 49
frames in the requested inclusive window; FFmpeg selected 48. The missing PTS
was exactly on the decimal start endpoint. Widening the diagnostic acquisition
envelope recovered the frame, but did not fix the shared decoder.

Python compared `float(pts * time_base)` with the requested seconds. FFmpeg's
`select=between(t,start,end)` computes its time expression differently. For the
observed source time base, a frame at the exact rational endpoint was rounded
below the start inside FFmpeg. The completeness guard then rejected the whole
window. This was a false acquisition failure, not an absent source frame or an
accepted incomplete sequence.

The new synthetic fixture reproduces the actual cadence, time base and nonzero
PTS origin in a small generated video. Before the fix, exact-start bounded and
EOF cases fail; the nearby inside/outside decimal cases pass: **2 failed,
2 passed**. No private images, names or validation labels enter the fixture.

## Fix and unchanged contracts

Interpret the public seconds arguments as decimal rational numbers. Compute
the first admissible source tick with `ceil(start / time_base)` and the last
with `floor(end / time_base)`. Compare the probe against those integer bounds,
and give FFmpeg the same integer `pts` bounds. Interior probe coverage checks
also use rational source time. EOF retains its explicit meaning.

The window remains inclusive. There is no timestamp rounding, epsilon, padding,
FPS conversion, rebasing or skipped frame. PTS, source/pixel hashes, decoder
completion, geometry, source mutation checks and exact probe/decoder sequence
equality are still mandatory. Incomplete, duplicate, reordered and truncated
inputs still fail closed. The full-video sampler is untouched.

This changes native decoder bytes and hence its existing recognizer
fingerprint. Old recognition output is not re-signed and old qualification is
not automatically valid. Source pixels can be compared between acquisitions,
but that comparison grants no recognition or event authority.

## Verification

| Check | Before | After |
| --- | ---: | ---: |
| Decimal endpoint fixture | 2 PASS / 2 FAIL | 4 PASS / 0 FAIL |
| Existing native input/replay plus endpoint tests | Not rerun as a combined baseline | 54 PASS |
| Real source, original inclusive window | 48 decoded / 49 expected; withheld | 49 decoded / 49 expected; verified |
| Real-source missing PTS | 1 | 0 |
| Pixel equality against previously verified expanded acquisition | Unavailable on rejected input | All 49 frames identical |
| Strict E2E gain | Unmeasured | Unmeasured |

The corrected real-source window completed in 235.44 seconds including source
hash checks. The exact private source/PTS/pixel/code metadata and original
failure remain in local diagnostics. The source image recognizer was not rerun
or relabeled in this acquisition check. No Full E2E was justified or executed.

Commands:

```bash
python3 -m pytest -q tests/unit/test_native_window_endpoint_precision.py tests/unit/test_native_source_input.py tests/unit/test_native_replay.py
python3 -m ruff check src tests
python3 -m mypy src
```

Local results: 54 tests passed in 43.22 seconds; Ruff passed; mypy passed all
133 source files. Remote checks verified source commit
`212dee0656e52191f0cbb3947e77f390594862c3`:

- Linux PR run `38954537575`: 3,741 passed, 7 skipped; coverage 86.60%; Ruff
  and mypy passed.
- Windows PR run `38954537622`: 3,737 passed, 11 skipped; coverage 86.54%;
  UTF-8-disabled checks 13 passed; Ruff, mypy, packaging and packaged smoke
  passed. Both run APIs report the exact source commit above and success.

The native endpoint regression tests execute with the installed FFmpeg on both
platforms; no existing failing assertion was skipped or weakened. These results
cover the code/test revision named above; this later report-only update does
not claim a different source revision was tested.

## Remaining S-01 work

This removes a reproducible source acquisition blocker. It does not qualify
Self identity, killer/victim roles, report absence or a Death transition.
Independent positive qualification, formal Event/Package/Trace connection and
same-condition canonical FAIL reduction remain required on the recognition
branch. The adopted Full 23/55/4 and archived unadopted Strict 28/50/4 are not
updated by this fix.
