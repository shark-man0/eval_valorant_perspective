# Qualified native timer to sampled snapshot transport

## Problem / root cause

Native lifecycle analysis retains original global timer displays, but the sampled
processor previously joined only boundary events. Native clock evidence could
not reach the sampled observation, RoundPackage snapshot and canonical trace.
This is relevant to `game_timer_display` predicates; it does not itself solve
round qualification, package scope or the R1 end timestamp.

## Change

After validating analyzer-owned native lifecycle inputs, the processor can now
copy a qualified native clock into a sampled observation at an exactly identical
PTS. It preserves the original display, seconds and reader provenance, requiring
both display and ROI confidence at least 0.90. It retains sampled timestamps,
state, identity, ownership and all player fields. Missing native clocks,
occlusion, incompatible states, preexisting display/provenance or conflicting
sampled numbers prevent the join. The native analysis is revalidated at terminal
processing as before. There is no saved-report runtime entrance, interpolation,
nearest-frame lookup, source-label injection or threshold change.

No default profile/qualification is adopted. A source-assured global route still
requires independent actual qualification. Existing qualifications are bound to
production code and cannot be reused after the code change.

## Tests

28 relevant unit/integration tests passed in 13.28 seconds; Ruff passed and mypy
passed on 121 source files. The new tests cover unknown identity without player
fact promotion, original display/provenance transport, exact-PTS abstention,
occlusion/weak/conflicting evidence, missing qualification and the processor →
package → trace chain. Synthetic qualification fixtures are not actual evidence.

## Actual-source binding limitation

The archived full E2E stores ffprobe display timestamps at six decimal places,
while native source observations use integer ticks at timebase 1/15360. Of the
108 real end-window native frames, none has a bit-identical timestamp in the
archived sampled observations; 31 match only after six-decimal formatting.
The current exact-PTS join therefore does not improve that full workload.
Formatting equivalence alone is not adopted as a frame-identity guarantee.

This is an incomplete transport implementation for the actual full pipeline,
not a measured canonical improvement. The next required change is preserving
decoder frame/tick identity in sampled extraction (including cached frames) and
joining by that verified identity while leaving sampler behavior and observable
sample timestamps unchanged. Unsupported legacy frames must abstain. PTS loss,
epoch breaks and conflicting evidence remain fail-closed.

## Previous / Current / Delta

Synthetic package/trace transport passes; actual exact-PTS overlap remains zero.
Canonical baseline 23 PASS / 55 FAIL / 4 NE, Current/Delta unavailable. No new
targeted/sampled/full canonical run; canonical negative/discontinuity outcomes
are not reverified. No actual qualification, boundary or PASS gain is claimed.
Windows execution remains unverified; implementation has no OS-specific branch.

## Decoder tick identity resolves the precision mismatch

Sampled extraction now retains ffprobe's integer `best_effort_timestamp` and
stream `time_base` alongside its existing decimal timestamp. The decoded image
index selects that source tick; no tick is inferred from FPS or decimal rounding.
Optional FrameSample identity binds the tick to the source video SHA256 and exact
JPEG SHA256. Partial identity, invalid timebase or a timestamp inconsistent with
ffprobe's decimal representation is rejected. The existing timestamp selection,
frame count, image preprocessing and emitted sample times are unchanged. Custom
backends or probes without integer ticks retain legacy frames without identity.

The actual processor now joins by video hash, integer tick and rational timebase,
and verifies sampled image bytes before joining and again before publishing the
processing result. With frame inputs, legacy frames without decoder identity
abstain even when their timestamps happen to match. A foreign source or mutated
image fails closed. No closest-time or formatted-timestamp fallback is used.

Decoded-frame cache format2 retains this identity and validates image/source
bindings on read and write. The cache key includes its format version, so old
entries are safe misses in a separate namespace rather than being overwritten
or interpreted as new proof. Frames with no identity remain cacheable, but cannot
supply this native timer join. No recognition output is cached.

### Actual-video verification

The 31 archived sampled timestamps within the existing 108-native-frame end
interval were extracted from the actual video using the common VideoService.
All31display timestamps remain bit-identical to the requested archived timestamps;
all31decoder ticks resolve to the corresponding native source row. Cache
put/get preserves all31identities. Three matched native rows contain existing
accepted original timer displays. Native input reports and archived full report
hashes are unchanged. This verifies source correspondence, not actual lifecycle
qualification, a current OCR prediction, or a released canonical snapshot.

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Actual source frame joins in the fixed workload | 0 | 31 | +31 |
| Changed sampled timestamps | 0 | 0 | 0 |

The source-binding diagnostic took262.425549sec, including a full ffprobe timeline
scan,31sample extractions and cache writes/reads. There is no comparable previous
runtime; this is not a full E2E or claimed speedup. Report:
`e2e_reports/match_001/decoder_tick_join_real.json`.

62related extraction/cache/native-merge/processor tests pass in14.13sec. Ruff
passes on source and the changed tests/cache module; mypy passes on121source files.
Tests cover integer probe ticks, unchanged decimal times, cache identity retention,
precision-different timer transport, wrong source, mutated JPEG, unsupported legacy
frames, and the existing package/trace and player-fact regressions.

Current actual source binding is now proven for this fixed workload. Independent
reader/lifecycle qualification and gated targeted/sampled/full evaluation remain
required; no real qualification is created and no original assertion status is
changed. Production fingerprint changes invalidate old code-bound qualification.
