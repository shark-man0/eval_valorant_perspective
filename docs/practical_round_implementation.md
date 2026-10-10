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

## Source-assured candidate producer checkpoint

`hud/practical_lifecycle.py` now collects provisional boundaries directly from
configured production readers on `NativeSourceFrame` pixels. It uses the existing
`UneditedUiStartTracker`, `UneditedUiEndTracker` and lifecycle state machine, with
explicit `boundary_mode="practical"`. Strict construction still requires its
qualification and preserves formal release semantics. No reader acceptance
threshold changes; no expected value or GT enters production. Practical transport
requires current-frame phase-presence measurements: older archives missing that
measurement cannot silently stand for phase absence.

The same source/owned-field admission checks are shared with the strict native
replay. Practical source gaps, epoch changes, repeated pixels and explicit breaks
reset pending transitions; they are not game boundaries. An independent end-only
sequence may produce a provisional end without inventing a start. Its candidate
timestamp is the first observed score change, confirmed by stable clock/score/
result observations, preserving the strict delayed-result tracker's timing rule.
Provisional provenance explicitly says qualification is unverified.

`HudVideoProcessor.process` and `process_frames` now accept explicit practical
mode and `PracticalLifecycleAnalysis`. Source SHA-256, input-contract file, current
profile and recognizer fingerprint are rechecked. Transport is replayed before
processing and before publication. Source breaks reach HUD, visual analysis and
Package association. Provisional global numbers are not merged into player-owned
facts or formal events. Existing strict entry-point defaults and builder arguments
remain compatible.

### Archived actual video evidence

The archive replay command below verifies the source video SHA-256 against the
explicit unedited contract and uses saved actual reader measurements. It does not
rerun recognition or create qualification. It normalizes only the collection-local
frame index; PTS, pixel hashes, displayed values and reader confidences are retained.

```bash
PYTHONPATH=.:src python3 scripts/diagnostics/replay_practical_lifecycle.py \
  --video ValorantData/videos/Valorant_09-25-2026_0-37-29-379.mp4 \
  --input-contract datasets/input_contracts/match_001.unedited.json \
  --output e2e_reports/match_001/practical_lifecycle_archive_replay.json \
  e2e_reports/match_001/r1_current_phase_presence_inputs.json \
  e2e_reports/match_001/r1_end_current_phase_inputs.json
```

| Boundary | Observed candidate time | Later confirmation | Status |
| --- | ---: | ---: | --- |
| R1 start | 4.102669270833333 | 4.202669270833334 | provisional |
| R1 end | 74.48600260416667 | 75.3693359375 | provisional |

R1 start preserves the original `0:00 → 2:25 → 1:39` observations and original
phase-disappearance timestamp. End evidence includes the accepted clock change,
old/new stable score and later stable result pixels. The timestamp is not selected
by distance to GT. These are two independently replayed local native windows; no
state is bridged across their unobserved middle. Full R1→R2 source continuity and
practical video-level Package association are not yet verified. Existing R2 reader
archives lack current-frame raw phase-presence fields and require a fresh current
producer scan before admission. The next task is the whole-video collection and
application/settings/GUI/resume integration, then separate accuracy evaluation.

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Saved observed R1 boundary candidates | 2 | 2 | 0 |
| Typed provisional archive records | 0 | 2 | +2 |
| Formal events released by archive replay | 0 | 0 | 0 |

Canonical full metrics are historical 23/55/4; no new canonical run was performed.
Neither this transport comparison nor the archived measurements prove ±0.1-second
precision or qualification. No assertion/expected value/window was modified.

### Producer checkpoint verification

New producer/transport tests: 14 PASS, including an opt-in processor integration
that produces two provisional starts, retains an unknown last end and emits no
formal boundary events. Full source mypy: 127 files PASS. Ruff across
src/tests/scripts/e2e and the new diagnostic script: PASS. The selected 142-test
native/start/end/processor regression run returned 141 PASS and one qualification
fingerprint failure because recognition code was updated while that run was
executing. With code frozen, that exact case was rerun and PASS (2.73 seconds);
the 14 producer tests were also rerun and PASS. This is not a claim of a full
pytest run or Windows CI execution. Production code should remain frozen during
fingerprint-sensitive test runs.

No new full E2E was needed for this transport checkpoint. Current strict E2E
results and ±0.1-second actual precision are unmeasured, not assumed unchanged
PASS results. Remaining application work: automatic verified native collection
for practical mode, settings/GUI opt-in and boundary labels, fingerprinted
checkpoint/resume, practical multi-event evaluation, real R2 current-phase scans,
continuous Match-level Package validation, full regression, CI and final PR.

## Application opt-in, GUI and resume checkpoint

The existing native collection orchestration now accepts explicit practical mode,
uses the same whole-source decoder/storage ceiling and per-frame binding/terminal
verification, then calls `collect_practical_lifecycle` instead of the qualified
formal producer. Strict collection remains the default. Missing input contracts
and changed source/profile/code are rejected before publishing results. This
reuses the existing decoder/Package pipeline; no second Round processing system
or production GT inputs were introduced.

App settings now persist:

- `round_boundary_mode`: strict by default, practical explicitly selected.
- `unedited_input_contract_path`: mandatory for practical real-HUD processing.
- `native_png_budget_mb`: bounded temporary native-image storage ceiling.

The settings dialog exposes mode, contract file and temporary storage ceiling.
It explains that provisional observations are saved while uncertain boundaries
remain unscored. Practical mode requires real HUD; mock input does not inherit
the video assurance contract. The actual video SHA-256 must match the selected
contract at runtime, so assurance is not automatically applied to other videos.

The pipeline passes the opt-in and native collection options. Its practical
resume fingerprint binds mode, options, input-contract file contents and current
recognizer code. Changing the mode or contract rejects resume. Package fingerprints
already include persisted lifecycle metadata. Uncertain packages skip AI evidence
frame planning as well as coaching; known observations/facts are saved. Resume
restores the same provisional boundary records/facts and does not reuse scored
results on uncertain context. Progress text explicitly says observations were
saved/restored with scoring deferred rather than saying they were evaluated.

The result screen shows interval start/end status as confirmed/provisional/unknown
and expands saved observations to display their original timer string, HP and
scores. Missing values stay missing. Interval numbers are storage/order keys.
Neither successful segmentation nor a displayed value increases Fact confidence.
The standard scored-evaluation aggregator and non-video features are unchanged.

Verification so far: 62 selected settings/GUI/native-provider/Package/pipeline tests
PASS. A follow-up 20-test set covering practical resume and existing mock pipeline
flows PASS. Full source mypy (127 files) and Ruff PASS. These are scoped regression
results, not full pytest or Windows CI certification. The GUI renderer was tested
with actual offscreen Qt widgets, retaining the existing audio-free test harness.

The consumer resume integration cancels after storing an actual synthetic
provisional-start Package, resumes, compares its boundary metadata and facts,
and verifies zero scored evaluations, zero AI-evidence frame requests and zero
clips. Source collection is separately tested with a synthetic decoder-owned
continuous two-round sequence through the real common collector and terminal
verification. No real video full run was added for these application contracts.

Remaining work includes automatic confirmed-boundary priority when valid
qualification is available, complete one-to-one practical precision metrics, fresh
current-reader R2 evidence and continuous real-video Package validation, Linux/
Windows CI, full regression and the final PR. The broad goal remains active.
