# Practical round segmentation implementation

## Scope and current checkpoint

Start main: `27c8465ef9dfa22afba623922e0fddef5d1fdade`, fetched/pulled
before work. Branch: `codex/practical-round-boundaries-20261011`.
Preexisting uncommitted score-label investigation documents/JSON and local
images are preserved. The user's Practical Mode instruction supersedes the old
requirement to stop all segmentation work until confirmed qualification exists.
The score witness discrepancy remains recorded; no expected value changes.

This checkpoint includes the transport model, single matched-boundary time
scoring primitive, opt-in Package partitioning, additive persisted schema and
conservative analysis admission. It is not yet a finished application mode or
real-video precision claim.
No main merge or PR has been made yet.

## Existing integration points

`BoundaryDecision` already separates first candidatePTS from
`evidence_provenance.confirmation_pts_sec`. `PendingUiStart` retains original
clock displays and the existing0.05second corroboration minimum. Assured source
tracking checks native cadence/PTS/epoch/pixel evidence separately from editing
assurance. Strict qualification and formal event release remain unchanged.

`RoundPackageBuilder._round_windows` already supports incomplete windows,
pre-round preparation association and source-break fragments. Its
`require_detected_rounds` switch affects absence of windows; it does not qualify
provisional boundaries. Incomplete windows already receive zero round-level
HUD/visual confidence and completeness. Reuse these mechanisms when connecting
practical segmentation; never append provisional starts/ends to formal events.

The Package schema now explicitly admits optional `round_lifecycle` metadata.
Strict packages omit it. SQLite stores complete PackageJSON and the new round-trip
test verifies that candidate times, status and provenance survive retrieval. Pipeline checkpoint/resume fingerprints, scoped rule
evaluation, AI suppression and GUI labels still require integration and tests.
Package numeric `round_no` must remain a storage/order key, with observed game
round numbering explicitly unknown when unproven.

## Boundary model

`rounds/boundaries.py` stores kind, confirmed/provisional/unknown status,
boundary time, later confirmation time, ordered evidence times, optional bounded
confidence and original provenance. Unknown carries no invented time/confidence.
The boundary timestamp must occur in actual evidence; confirmation does not
replace it. Candidate conversion always yields provisional, even if an attribute
contains a qualification hash. This model validates transport only; it does not
itself attest continuity or authorize formal confirmed events. Producer and
consumer admission must still enforce those contracts.

## Separate accuracy evaluation

`scripts/e2e/practical_accuracy.py` evaluates one externally matched boundary
using `abs(boundary_time - truth_time) <= 0.1`. The tolerance is evaluator-only,
independent of confirmation delay; no predicted time is rounded. Missing or
wrong-kind predictionsFAIL; absent independent truthNE. Float subtraction
roundoff at the inclusive endpoint is handled at1e-12only. A complete one-to-one
multi-boundary matcher and false-positive/detection-rate summary remain to build.
The original82assertions and canonical evaluator are unchanged.

## Tests and remaining work

Fifty-three focused model/accuracy/Package/temporal-scope tests PASS; a separate
149-test lifecycle/schema/storage regression set also passes (202 total). After
refactoring the schema definitions, the 14 Package tests were rerun and pass.
Ruff across src/tests/scripts/e2e passes; full source mypy passes (126 files). Synthetic delayed confirmation, timestamp ordering,
unknown preservation, serialization, bounded confidence, inclusive tolerance
and wrong event kind are covered. No new video/E2E run is needed for this model
checkpoint; real practical precision remains unverified.

Next: connect producer-owned source-assured candidates to application opt-in
segmentation and settings/GUI/resume. The builder accepts already admitted
candidates; transport validity is not reader qualification or source attestation. Then replay
existing actual continuous evidence and compare strict/practical metrics without
promoting provisional events or changing GT. Linux/Windows CI, full regression,
dedicated commit and PR remain outstanding. Windows execution is unverified.

## Package partition and analysis contract

`RoundPackageBuilder.build(boundary_mode="practical",
provisional_boundaries=...)` explicitly opts into candidate partitioning.
The strict default rejects supplied provisional candidates. Partition descriptors
reuse `_round_windows` for existing pre/post-round context, observation gaps and
source-cut fragmentation, but never enter the Package `events` collection.
Confirmed metadata refers to an existing formal event ID of the correct kind;
caller-supplied confirmed observations cannot qualify themselves.

Metadata records independent start/end statuses, optional candidate payloads,
and formal event IDs. `observed_round_no` remains null; the required `round_no`
is a chronological storage key, not an inferred in-game number. Missing boundaries
remain unknown. Repeated identical candidates are suppressed; competing same-kind
candidates without an intervening opposite boundary and simultaneous opposite
candidates are withheld. Evidence spanning a supplied source cut is rejected.
No production segmentation tolerance is derived from the evaluator's ±0.1 seconds.

Every practical Package with an unconfirmed endpoint receives zero round-level
HUD/visual confidence and completeness, preserving the existing fragment policy.
Individual observations/facts are retained. `RoundAnalyzer` conservatively returns
a valid, unevaluated result without invoking Rule Engine or AI Coach for such a
Package. This avoids scoring uncertain whole-round context. Admission of individual
boundary-independent rules remains future work; the current guard intentionally
defers all coaching on uncertain Packages. Confirmed-only practical Packages use
the ordinary analysis path.

Canonical full results remain the last measured 23 PASS / 55 FAIL / 4 NE.
No new full run has been performed; these are historical values, not a measured
result of this implementation. Real-video practical boundaries, false-positive
counts and ±0.1-second precision remain unverified. GUI mode/labels, native
producer integration and complete practical multi-event evaluation remain open.

This is a tested branch checkpoint, not completion of the Practical Mode goal.
Remote main still equals the recorded start SHA at checkpoint fetch; no merge
conflict was present. A final PR and Linux/Windows CI review remain outstanding.
