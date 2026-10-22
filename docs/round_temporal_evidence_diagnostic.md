# Offline Round transition evidence association

This diagnostic associates Result, Score and Timer observations from one native
source. It does not publish Round End, estimate internal game End, qualify a
recognizer, or change production readers and lifecycle policy.

## Inputs and boundaries

Keep source identity, integer native PTS, rational timebase, acquisition epoch,
frame/pixel hashes and measured native cadence on every observation. The CLI
requires a DEVELOPMENT source from the existing private review-session registry:

```sh
python -m scripts.diagnostics.round_transition_evidence \
  --review-session /private/review-session \
  --input /private/normalized-observations.json \
  --output /private/new-temporal-evidence.json
```

Reader evidence contains original `value` and `confidence` for `ally_score`,
`enemy_score`, `timer` and `result`. Geometry consistency, expected cadence and
optional buy-phase/discontinuity flags are diagnostic context. The input is an
observation ledger, not a new GT system. Source/GT contracts remain unchanged.
Output creation is exclusive, private and recorded in the existing Exposure
journal. No decoder or prediction cache is implemented here.

A source/hash/timebase mismatch, duplicate PTS within an acquisition, invalid
native binding or non-DEVELOPMENT declaration is rejected. Different epochs and
missing native frames are never stitched into continuous evidence. A scene's
visual continuity remains UNVERIFIED even when PTS cadence is regular.

An adjacent score increment can collect repeated exact Result words in the same
native segment, with fixed six-second offline association horizon. Geometry must
support the score endpoints and at least two word observations. The existing
0.90 text threshold and exact vocabulary remain unchanged. Timer observations
must be available and nonincreasing within display quantization. A different
word, timer contradiction, preparation overlap or missing support keeps UNKNOWN.

Readability holes do not become guessed words and do not automatically create
multiple physical events. Each candidate records the unread frames and original
witnesses. Exact score-bracket replays are deduplicated while retaining separate
acquisitions; disagreeing replays become UNKNOWN. Result-only groups remain
UNKNOWN. Candidate IDs identify evidence proposals, not physical event IDs.

The first readable-word bracket is separate from partial/complete visual display
observations. Human or AI visual observations must retain their origin and local
review receipt. OCR alone never proves display completeness. Last Active, partial
Result, confirmed complete display, score-change interval and next-round witnesses
must remain separate in a private companion ledger. Unobserved time is not a
negative; no midpoint or backdated internal End is generated.

## Score configuration preflight

A historical private Profile used a foreground preprocessing name that current
code does not support. Both Score roles then returned a configuration failure on
all 304 existing development images (608 attempts). These are configuration
errors, not 608 image-recognition failures.

`score_readers(profile_path)` now makes that condition an explicit preflight
error. An alternate supported mode requires a separate explicit declaration:

```python
readers, binding = score_readers(
    private_profile_path, foreground="white200_rowcontrast_v1",
)
```

This uses the existing production implementation as an offline reader instance;
no production configuration or old Profile is edited. The parent and template
hashes are bound, and the loader still enforces 0.90 confidence and 0.04 class
margin. Unsupported names never alias or fall back silently. Keep original,
legacy OCR and explicitly supported streams separate; do not choose a successful
reader per frame.

The explicit supported condition produced 536 numeric observations out of 608
attempts on the same development images; 72 remained rejected. Both scores were
read on all 121 frames of the known transition. These are diagnostic counts,
not independently verified digit accuracy. The original Profile still fails
closed and is preserved for reproduction.

## Development findings and limits

Two previously accepted Result images rejected by the structured crop were
human-confirmed complete THRIFTY displays. They are crop over-rejections, not
reasons to lower the threshold. Temporal association retains their UNKNOWN image
observations while using the surrounding independent score/timer evidence.

A separate adjacent-image review confirmed no Result, partial Result, then no
Result. The partial display preceded the score update. This prevents confusing
stable OCR readability onset with the earliest display or internal End.

New bounded development follow-up distinguishes a WON case with score change and
compatible timer from a LOST case with score change but unavailable timer and
untrusted geometry. The latter remains UNKNOWN. Short, separated reobservations
are context only, not continuous onset evidence or independent qualification.

Production Matcher/Profile, Canonical GT/tolerances, Self Death and Map/Visual
code are outside this diagnostic. Private frames, timestamps, responses and
Profiles must not be committed. Continue the HUD development branch without
merging to main until a functional milestone is ready.
