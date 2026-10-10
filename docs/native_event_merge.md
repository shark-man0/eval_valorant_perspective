# Native system boundary merge into sampled processing

## Problem and evidence

The explicit qualified native entrance produced schema-shaped system boundaries,
but normal `HudVideoProcessor` processing did not accept them. Its package builder
also looked only at sampled observations for preparation context. Synthetic merge
testing exposed an extra leading partial package when native preparation evidence
was unavailable at sampled timestamps. Replacing sampled HUD values would conflate
global lifecycle evidence with player ownership and would change the sampler's
meaning.

## Contract change

Both `HudVideoProcessor.process` and `process_frames` now accept an optional
in-memory `native_lifecycle` result from the production native entrance. Existing
calls, default sampler, output schema, recognition thresholds and assertions remain
unchanged. There is no saved event/GT JSON input option.

Before sampled processing and again before returning its result, the receiver:

- loads matching current paired qualification and rejects profile drift since
  analyzer construction;
- hashes the actual source video and checks native video identity;
- checks the result's qualification/code/profile binding, including empty-event
  results, so stale recognition cannot be silently reused;
- verifies one native epoch/timebase, increasing uniform cadence, actual tick/time
  relation and scene/UI source-pair identity;
- replays the qualified global lifecycle and requires identical public events;
- accepts only system round boundaries from the native path, leaving sampled
  player observations untouched; identical duplicates are suppressed, while
  competing sampled boundaries or event ID collisions are rejected.

The merged events enter the existing visual context, event contract/fusion,
RoundPackage builder and trace path. Source/report changes during package building
withhold the entire processing result. No source geometry or ownership is copied
from a later frame or from native observations onto sampled frames.

The builder can now use native boundary preparation provenance for context
membership: qualified source hashes/code/profile/epoch and a segment-local
preparation interval satisfying the existing duration/gap policy. It does not
create sampled observations or alter HP/timer values. The initial preparation
belongs to the first detected round; preparation following a prior end belongs
to the upcoming round. Invalid, short, future, weak or source-unbound preparation
cannot suppress an existing leading partial fragment.

Qualification fingerprints now include the application processor and package
builder as well as existing producer/decoder code. Historical reports remain
historical and are not resigned after this change.

## Tests

227 related unit/integration tests pass in82.72seconds; Ruff passes; mypy passes
for116source files. New synthetic tests cover qualified replay, stale empty-event
transport, source/PTS/pixel/UI/ownership tampering, conflicting boundaries,
duplicate suppression, standard processing into two packages, preparation context,
preservation of sampled HP/timestamps/frame count and snapshots, actor/time/attribute
transport through trace, and terminal video/qualification mutation.

The tests caught an extra leading partial package and verified its correction.
They also retain the existing default processor and package/lifecycle regression
tests. Positive clocks, source witnesses and qualification are synthetic; these
are integration contracts, not real-image qualification or canonical PASS gains.

## Independent image evidence and continuity decision

`e2e_reports/match_001/native_event_merge_guard.json` checks four existing native
pixel hashes and attempts to pass their unqualified diagnostic fixture through
the normal receiver. It is rejected with `qualified native analyzer required`,
releasing no event/package. This is a negative receiver test, not a production
saved-report loader or a new video decode. The current R1 scene/foreground/UI
continuity decision remains unqualified and fail-closed.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Synthetic normal-processing native boundary packages | no merge route | 2 | contract test only |
| Synthetic normal-processing sampled frame count | 6 | 6 | 0 |
| Synthetic sampled HP facts preserved | 6 | 6 | 0 |
| Actual unqualified receiver events/packages released | no route | 0 / 0 | negative guard only |
| Adopted real paired qualification | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | unmeasured | unmeasured |
| Canonical negative failures / discontinuity violations | 0 / 0 | unmeasured | unmeasured |

## Remaining blocker

No real supported phase-absence reference or independent scene/foreground/UI
qualification was adopted. Canonical targeted/sampled/full E2E was not run because
no qualified boundary candidate exists. The automatic native stream/provider and
its full-video acquisition/EOF/state continuity still need implementation before
standard CLI activation; the explicit merge API does not complete that work.
Next obtain independently qualified real source/UI evidence, then activate native
delivery through the shared Python orchestration. Windows hardware/FFmpeg/PTS/OCR
behavior remains unverified. All82assertion records and validation data are intact.
