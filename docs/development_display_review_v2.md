# Development display review v2.1

`scripts.diagnostics.display_review_scope.validate_display_review` validates
explicit source-bound human reports for offline development. It does not replace
Temporal GT v1, write GT, decode media, qualify a recognizer, or emit events.
It has no production caller. Version 2.1 adds disappearance and review scope to
the private v2 proposal; old answers must remain unchanged.

## Concepts

| Observation | Required report | Does not establish |
| --- | --- | --- |
| Result presence | Reviewed point with PRESENT, PARTIAL, or COMPLETE | New appearance or internal End |
| Result appearance | Explicit ABSENT → visible endpoint bracket | First complete display or internal End |
| Result disappearance | Explicit visible → ABSENT endpoint bracket | A new physical round |
| Complete display | Explicit PARTIAL → COMPLETE endpoint bracket | First appearance |
| Score before / after | Independently reviewed point values | A change event without an explicit bracket claim |
| Score change bracket | Explicit different fully read Score pairs | Result appearance or internal End |
| Interval negative | Explicit NO plus FULL continuous interval review | Population false positive rate |
| Internal game End | Always null | Video display timing is not an internal game clock |

A bracket records observed endpoints and uncertainty, not a midpoint. It may
contain multiple changes; physical event counts and episode identity remain
unset. A point answer never creates a bracket. Result OCR failure is not visual
absence. Partial or unreviewed intervals never become negative labels.

## Caller responsibilities

Before making a packet, use the existing registry and exposure ledger to admit
DEVELOPMENT sources. Verify the original source SHA and actual encoded/pixel
frame bytes using the existing native acquisition path. Freeze the packet hash
outside the response. Metadata validation alone cannot establish source
admission, absence of edits, visual continuity, human attention or label truth.
Do not use this module to open protected evaluation media.

Keep packets, frames, responses, PTS, profiles and labels private. Record
source-only human review separately from prediction exposure. A UI hiding
predictions does not restore independence to an exposed development source.
Nothing here promotes data into qualification GT.

```python
from scripts.diagnostics.display_review_scope import validate_display_review

observations = validate_display_review(
    packet, response, trusted_packet_sha256=externally_frozen_packet_sha256
)
```

The caller must retain the immutable packet, raw response, validation output and
their hashes. The validator does not read paths or save files.

## Wire format

Packet kind is `development_display_review_packet_v2_1`. Its `cases` list has
unique `id` values. Each case has a nonempty ordered `frames` list with unique
frame IDs and these required fields:

* `source_id`, `source_sha256`
* Native integer `tick`, positive rational string `time_base`, acquisition `epoch`
* `encoded_sha256`, `pixel_sha256`
* Positive integer native `expected_step_ticks`
* Optional boolean `discontinuity` marking a cut before that frame

Use the actual native ledger, including frames not sampled by a reader. Missing
native ticks, epoch switches and explicit cuts block continuous interval claims.
This is conservative for variable cadence: unresolved timing stays UNKNOWN.
One case must have one source SHA and timebase. Duplicate PTS within an epoch
or a changed trusted packet are rejected.

Response kind is `development_display_review_response_v2_1`, with
`origin: "human"`, a nonblank `reviewer`, `packet_sha256`,
`internal_End_tick: null`, `formal_events: []`, and the exact case IDs.
Each case supplies all four lists:

* `points`: unique `id`, `frame_id`, boolean `reviewed`,
  `result_state` (ABSENT/PRESENT/PARTIAL/COMPLETE/UNKNOWN), optional `score`
  (null or two integer/null values). One response per frame. Missing digits
  stay null. Unreviewed raw claims are preserved but exposed as UNKNOWN/null.
* `scopes`: unique `id`, frame IDs `start` and `end`,
  `coverage` (FULL/PARTIAL/UNKNOWN), boolean `full_interval_reviewed`.
  A full claim needs at least two continuously acquired frames and both flags.
* `boundaries`: unique `id`, `kind`, point IDs `before` and `after`.
  Kinds are RESULT_APPEARANCE, RESULT_DISAPPEARANCE, RESULT_COMPLETE and
  SCORE_CHANGE. Both endpoints must be reviewed, ordered, continuous and have
  different pixel hashes. Insufficient state evidence stays UNKNOWN.
* `interval_claims`: `kind`, `scope_id`, `occurred` (YES/NO/UNKNOWN).
  Only explicit NO in an eligible full scope can support an interval negative.
  Contradictory reviewed points veto that negative without generating an event.
  A YES interval answer alone cannot supply the missing endpoint bracket.

Synthetic examples and invalid-input cases are in
`tests/unit/test_display_review_scope.py`. Source cuts and timestamp stress in
those tests do not constitute natural-negative video coverage.

## Legacy answers

Retain the old question wording, raw answers and original scope. A legacy YES
to an ambiguous "newly appeared" question cannot automatically become either a
presence label or a verified appearance bracket. A newer point-presence answer
can be reported as a point only; it does not rewrite the old answer. A raw NO
with unchecked full review remains an unvalidated interval claim.

Migration previews should be separate records, with unknown disappearance,
unprovided Score digits and unselected endpoints. They must not fabricate new
human responses or silently update canonical data. New unanswered fields need
a fresh private review, or remain UNKNOWN.

## Limits and qualification

Outputs are `development_display_observations_NOT_GT`, with internal End null,
formal events empty, approval/qualification false and population accuracy null.
Even a validated human bracket remains a development report. Qualification
requires a separately approved independent dataset, recognizer/profile freeze,
review coverage, match independence, native continuity audit and explicit
miss/false-positive/UNKNOWN definitions. Existing GT and tolerances are unchanged.
