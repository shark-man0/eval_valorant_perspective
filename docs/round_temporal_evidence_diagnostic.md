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

## Score/Result ordering and residual-display safety

The same diagnostic now searches on both sides of the adjacent Score boundary.
Backward search is limited to the same measured pre-change score and the existing
six-second horizon. An unread Score, another Score, acquisition boundary, native
gap or source discontinuity stops that backward search. Exact words before and
after Score belong to one proposal keyed by the same native Score bracket; they
are not counted as two physical transitions.

Pre-Score OCR needs a reviewed absent-display witness before its first word.
Otherwise it might be residual Result from an earlier transition and the proposal
remains `UNKNOWN` (`pre_result_onset_unverified`). An unread OCR result is never
absence. This additional safety condition does not request new human reviews:
automatic diagnosis and UNKNOWN reports continue without them. Geometry-supported
word repetition, score endpoint geometry and Timer evidence still apply. Two
consecutive observations of each Score state are required around the boundary to
reject transient Score flicker. This is an offline evidence guard, not a change
to a reader threshold or Canonical GT tolerance. Stable but wrong Score readings
remain possible; persistence is not digit correctness or qualification.

Optional `visual_result` observations retain `state` (`NONE`, `PARTIAL`,
`COMPLETE`, `UNKNOWN`), optional exact `word`, `origin: human`, `reviewer` and
`review_sha256`. The importing workflow must validate the original review packet,
receipt and frame hashes before adding these observations. These receipt-bound
observations remain separate from OCR supports. An unspecified partial word has
`UNKNOWN_CONTENT`: it records temporal context but does not establish that it is
the same textual Result. No partial label is completed or converted into a word.
Reviewed NONE-to-PARTIAL intervals are observations, not guaranteed first onset.
Reviewed complete points likewise do not establish the earliest complete display.

The output separately records pre/post word ticks, ordering, partial observation
brackets, score persistence, endpoint timer values and original visual receipts.
Words with unread Score retain per-frame UNKNOWN and cannot support a proposal.
Two remaining trusted word observations are still required. Buy-phase overlap,
conflicting visual words, insufficient support, Timer reversal/reset or a word
episode shared by multiple Score increments keeps the proposal UNKNOWN. Cross-Score clock drops are recorded without inferring an internal End;
clock increases remain contradictory. Result support is never borrowed from a
different acquisition. Replays retain their own witnesses, without stitching.

A Result-only window, missing last Active or unobserved next purchase phase is
still incomplete evidence. Spectator/Death/Menu safety is not established merely
by regular native cadence or successful geometry. Use the private companion
ledger to retain those UNKNOWN states and separate acquisitions.

WON/LOST must also agree with which declared ally/enemy Score role incremented.
A disagreement remains UNKNOWN. This check assumes the Profile's role bindings;
it does not verify team identity on a Spectator screen. Unknown or wrong role
ownership still prevents semantic correctness/qualification claims.

## End through purchase and the next active clock

`scripts.diagnostics.round_lifecycle_evidence` extends the same private input and
DEVELOPMENT admission/Exposure/output contracts. It reuses the End integrator;
it does not change its Result/Score/Timer guards or publish runtime events:

```sh
python -m scripts.diagnostics.round_lifecycle_evidence \
  --review-session /private/review-session \
  --input /private/native-observations.json \
  --output /private/new-lifecycle-evidence.json
```

Supply the complete native coverage ledger for an explicitly bounded acquisition.
Frames not analysed have null reader values and unknown geometry; they are not
negatives. Retain every PTS/hash/epoch even if only a fixed fraction of native
frames are saved and read. Existing observations may be reused only after source,
PTS, timebase and decoded pixel hash agree with the new acquisition. Preserve
their original witnesses; a new epoch comes from a new continuous acquisition,
never from relabelling separate old windows. PTS regularity does not prove visual
continuity. Source cuts, missing frames and different epochs split association.

After the existing Score/Result End proposal, the offline assembler looks for
repeated purchase-banner observations with accepted Score, trusted geometry and
a clock from 0 through 45 seconds. It keeps the same Score until the next clock
reset. Purchase countdown and next-active-clock observations must agree with
elapsed native time and clock quantization. Two observations no more than one
second apart support a phase; association stops after 90 seconds. These are
explicit offline bounds, not changes to canonical tolerances or runtime policy.
A later accepted different Score stops search; missing Score stays visible as
UNKNOWN. Timer contradictions, untrusted geometry, incomplete End or unavailable
purchase/start evidence keep the lifecycle UNKNOWN.

The output distinguishes a purchase support interval from true purchase onset,
and the last accepted countdown/first repeated active clock bracket from actual
Round Start. A clock of at least 60 seconds is only an active-display hypothesis.
A partial Result, first readable word, reviewed complete word, Score bracket and
next clock bracket remain separate. Internal End/Start timestamps are always
null. No meaning is assigned to unanalysed frames or hidden menu contents.

`review_scores(packet, response)` validates a packet-bound human transcription of
screen-left/right Score digits. No predictions are used as default answers. The
import workflow checks original frame hashes before using the returned witness.
Optional `human_score_observation` retains that witness and receipt on an exact
source/PTS/timebase/pixel match. A known human/reader disagreement vetoes the
lifecycle; human digits never replace reader values or certify missing geometry.
Unknown digits stay unknown. Targeted DEVELOPMENT confirmation is not population
digit accuracy, team ownership, Human GT creation or independent qualification.

A bounded real DEVELOPMENT acquisition associated one known End proposal with
purchase and a next-clock reset using unchanged global calibration. Short old
acquisitions remain incomplete. Acquisition-local upper-HUD support was tested
privately but did not improve this lifecycle and was not adopted. Menu occlusion
and dynamic top-HUD changes therefore still produce UNKNOWN geometry. No
Production Matcher/Profile, threshold, Canonical GT or ownership rule changed.

## Transient next-clock displays and bounded Timer proposals

The lifecycle assembler now retains a contradictory initial clock prefix as an
UNKNOWN episode instead of stopping at the first pair of readable values. A
later pair may support a new display hypothesis only when it satisfies the same
Score, geometry, timing, one-second repetition and native-segment conditions.
The rejected prefix, its original values, hashes and contradiction bracket stay
in `rejected_clock_prefixes`. This does not repair the values, identify an OCR
error, or backdate onset into the prefix. Without later consistent observations,
the lifecycle remains UNKNOWN. Reappearing preparation clears the pending active
clock hypothesis; it must never produce a reversed countdown/reset bracket.

The existing relative `title_region` proposal was compared privately on the outer
Timer ROI, retaining strict glyph/punctuation/0.90 confidence/0.04 margin guards.
It recovered some points but regressed on another DEVELOPMENT recording and did
not improve lifecycle recovery. It was not adopted. Whole-ROI foreground removal
also regressed and was discarded. Current readers and Profiles remain unchanged.
Non-colon displays stay unread; no assumed minute/second value is substituted.
Keep acquisition improvements, temporal integration changes and rejected reader
experiments separate in reporting. An extra readable point is not independently
verified digit accuracy or a completed lifecycle.
