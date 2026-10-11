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

## Confirmed priority and separate multi-boundary accuracy checkpoint

### Problem and change

Practical collection previously retained all candidates as provisional even when
valid formal qualification was available. It now snapshots the configured
qualification and replays the unchanged Strict producer on the same native rows.
Only events actually released by that replay are admitted as confirmed. A
start-only qualification cannot confirm an end or re-arm the next formal round
through an unqualified end. Result evidence is removed from this formal overlay
unless both score and result components qualify. Practical candidates remain
available independently; existing builder priority gives a matching formal event
precedence without inserting provisional events into the formal event stream.

Missing or stale qualification yields no formal overlay, rather than promoting
candidates or stopping provisional segmentation. Changed qualification file bytes
invalidate the transport; validation replays and compares the complete formal
payload, including actor, to reject mutation. A whole-epoch Strict replay failure
also prevents formal release while source-safe practical observations remain
provisional. This does not relax Strict thresholds or discontinuity policy.

### Separate practical accuracy evaluation

`python3 -m scripts.e2e.practical_accuracy` writes a separate report:

```bash
PYTHONPATH=.:src python3 -m scripts.e2e.practical_accuracy \
  --predictions exported_boundaries.json \
  --truth independently_reviewed_boundaries.json \
  --output practical_accuracy.json
```

The prediction object contains `boundaries`, each a serialized
`BoundaryObservation`. The independent evaluator-only truth object contains
`boundaries` with unique `id`, `kind`, and `time_sec` (nullable), plus an optional
`complete_review` boolean. This is an explicit interchange format, not an
implicit conversion of Validation Pack acceptance windows to exact timestamps.
Do not supply GT to the production collection process. No midpoint, rounded
prediction or synthetic exact truth is generated.

Association preserves chronological order and uses each observation once. It
maximizes same-kind correspondences within an evaluator association radius
(default 1 second), then minimizes time error. That radius does not change the
±0.1-second accuracy criterion or production confirmation policy. Confirmation
latency is excluded from boundary-time error. Duplicates and wrong kinds cannot
receive extra PASS results. Unmatched predictions count as false positives only
when the caller declares exhaustive boundary review and all reviewed truth times
are known. Otherwise they remain unverified/NE; missing truth times remain NE.
The report records input hashes, per-boundary errors, separate PASS/FAIL/NE,
detection and time-accuracy rates, and confirmed/provisional/unknown counts.
These counts describe this separate evaluation, not the canonical 82 assertions.
An order-preserving iterative matcher avoids recursion limits on long recordings.

### Evidence and tests

40 focused producer/application/accuracy tests PASS (18.69 seconds), including
valid/missing/stale qualification, mixed confirmed/provisional boundaries,
formal actor tamper rejection, delayed confirmation, duplicate predictions,
wrong-kind matching, crossing-order rejection, incomplete point truth and CLI
input immutability/hash reporting. Full source mypy previously completed with
127 files PASS; Ruff across src/tests/scripts/e2e PASS. All new qualification
fixtures are synthetic and are not qualification of real-video readers.

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Canonical full PASS / FAIL / NE | 23 / 55 / 4 | Not rerun | Not measured |
| Actual-video ±0.1-second accuracy | Unverified | Unverified | Not measured |
| Formal release in archived practical replay | 0 | No new replay | Not measured |
| Automatic valid qualification overlay | Absent | Implemented and tested | Added |
| Separate one-to-one accuracy report CLI | Absent | Implemented and tested | Added |

No full E2E was run for this transport/evaluator checkpoint. Remaining work:
fresh R2 current-phase observations, continuous real-video Package validation,
practical report export from application outputs, independent reviewed point
truth where available, full regression, Linux/Windows CI and final PR. Formal
qualification on the actual source is still unproven; provisional segmentation
must not be reported as Strict acceptance or verified timing precision.

The subsequent frozen-code Strict/native/boundary regression selection completed
with 188 PASS in 115.68 seconds. `git diff --check` and Ruff also passed. This
selection does not establish new canonical E2E results or Windows CI status.

## Saved Package to practical accuracy report

The separate accuracy command also accepts saved common-processing output:

```bash
PYTHONPATH=.:src python3 -m scripts.e2e.practical_accuracy \
  --packages raw_processing.json \
  --truth independently_reviewed_boundaries.json \
  --output practical_accuracy.json
```

The input object must contain `round_packages`. The exporter validates canonical
Package Schema, rejects mixed sources/matches and overlapping intervals, retains
formal event actor/provenance, and preserves original provisional boundary and
confirmation times. Identical formal event IDs shared between Packages are
exported once; conflicting content for one ID is rejected. Distinct formal IDs
remain distinct so duplicate events can still fail evaluation. Exact matching
formal evidence takes precedence over provisional candidates. Unknown endpoint
records contain no timestamp or confidence; neither fragment edge becomes an
invented Round boundary. The export never modifies Package events or observations.

Report metadata includes partition windows/statuses, Package count, provisional
Package count and uncertain Package count. Interval numbers remain storage keys.
Confirmed in this transport means the existing formal event contract, not new
reader qualification or a practical PASS. These records stay outside the
canonical trace adapter and original 82 assertion results.

Verification: 32 saved-Package/export/accuracy/builder tests PASS in 21.61 seconds;
Ruff and diff whitespace checks PASS. No production source changed in this
checkpoint, so the preceding full-source mypy result still covers production.
The synthetic CLI test exercises saved provisional Packages through the separate
accuracy report while checking zero confirmed boundaries and original candidate
confidence/time preservation.

The latest normal canonical full run's saved Package was also exported without
fresh recognition. `e2e_reports/match_001/practical_legacy_package_export.json`
binds the raw input hash and records its one legacy partial Package as two
unknown endpoints, zero invented boundaries. This verifies compatibility with
actual saved data; it does not establish current real-video segmentation or
±0.1-second precision.

| Metric | Previous saved canonical run | Current export | Delta |
| --- | ---: | ---: | ---: |
| Packages | 1 partial | 1 partial | 0 |
| Detected formal start/end | 0 / 0 | 0 / 0 | 0 / 0 |
| Unknown endpoint records | Not represented separately | 2 | Newly exposed |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | Not rerun | Not measured |

Remaining practical acceptance work is actual current-reader R2 evidence,
continuous real-video Package collection, independently reviewed point-time
accuracy where available, full regression/CI and PR. Existing local-window
archive candidates are evidence to reuse, not evidence of whole-match validation.

## R2 current-phase native diagnostic

### Problem and evidence

The older R2 archive lacked explicit current-frame phase presence/confidence;
absence could not safely be inferred from a missing field. A new actual common
analyzer run decoded the explicit development window 111.186003–111.686003 seconds
at native cadence (30 frames, 256 ticks at timebase 1/15360). Its separate short
geometry prefix is calibration context, not temporal corroboration. Existing
profile/readers and thresholds were reused without GT inputs or new references.

All 30 current-frame phase scans were valid. Phase was present in 13 frames and
first absent at 111.4193359375 seconds, while the timer still displayed `0:00`.
Following observations preserved `1:40`, then `1:39`; the same R1 unedited-input
contract produced one provisional start at the original phase disappearance,
confirmed as a candidate at 111.48600260416667 seconds. Candidate confidence
was 0.931477963924408. Confirmation delay is approximately 0.066667 seconds;
it is not the boundary timestamp. No formal event or end candidate was released.
The local replay had zero source breaks and ended in `round_active`.

Artifacts:

- `e2e_reports/match_001/r2_current_phase_presence_inputs.json`: fresh current
  analyzer observations with native PTS/pixel hashes and explicit UI measurements.
- `e2e_reports/match_001/r2_practical_current_phase_replay.json`: source-contract
  validated practical replay, one provisional start and zero formal events.
- `e2e_reports/match_001/r2_practical_current_phase_comparison.json`: fixed-window
  comparison and binding to existing manual development review.

### Previous / Current / Delta

| Metric | Previous same R2 diagnostic | Current | Delta |
| --- | ---: | ---: | ---: |
| Native frames | 30 | 30 | 0 |
| Start candidates | 1 | 1 provisional | 0 |
| Formal events | 0 | 0 | 0 |
| Timer correct | 24 | 24 | 0 |
| Timer unknown | 6 | 6 | 0 |
| Timer wrong | 0 | 0 | 0 |
| Valid phase scans | 30 | 30 | 0 |
| Wall time (seconds) | 62.405189 | 80.368548 | +17.963359 |

Runtime reflects different instrumentation/code and is descriptive, not a speed
improvement. Timer labels were reused only after verifying the original reviewed
result hash, encoded-frame review binding, and exact decoded pixels/PTS/timebase
against the fresh run. PNG encoding hashes differed, while all decoded pixels
matched; encoded-byte equality was not falsely asserted. This remains an existing
post-prediction development review, not independent holdout qualification.

### Decision and remaining blocker

The R1 practical phase-disappearance/clock-stabilization contract applies to the
observed R2 sequence without timestamp special cases. No production change was
needed. R2 timing precision against an independent exact truth remains unverified;
no acceptance-window midpoint was used. Zero end candidates in this local start
window does not prove no false R2 end across the whole video. R1-to-R2 continuity,
the wider 109–114-second negative/context interval and whole-match Package
validation remain open. The canonical 23 PASS / 55 FAIL / 4 NE run was not
reexecuted, so no canonical delta is claimed.

## Wider R2 continuity and unknown-context preservation

### Problem and evidence

A fresh current analyzer run processed every native frame in 109–114 seconds:
300 frames, 300 valid phase scans, 228 accepted timer displays, 198 available
score pairs, zero result matches. Observed states were buy menu 43, unknown 228,
and live 29. The practical replay produced exactly one start candidate at
111.4193359375 seconds, confirmation 111.48600260416667, no end candidate, zero
local source breaks, and final state `round_active`. Runtime was 581.167058
seconds. This wider context did not create menu-triggered or duplicate starts.
The calibration prefix remains separate from temporal evidence.

Passing these actual observations to the common Package builder exposed a
preservation bug: context outside the existing trusted round windows was dropped.
Only 181 of the 300 observed timestamps fell inside the initial output Package.
The discarded prefix included purchase-menu observations; safely assigning those
observations to the detected round had not been established.

### Contract change

Practical mode now retains previously unassigned observed context as partial
windows with both boundary statuses unknown. Existing windows retain priority.
Explicit source cuts and observation gaps greater than one second split these
storage fragments; their endpoints are never converted to round events.
Unknown-only input can therefore be stored without inventing gameplay identity,
round start, round end, or round number. Strict mode does not call this retention
path. Uncertain fragments keep zero timeline completeness and remain unscored.
This is context preservation, not an assertion that the earlier menu belongs to
R2. No safety threshold or formal boundary qualification changed.

Actual archived-current-reader replay through the updated builder retains all
300 timestamps in nonoverlapping storage windows:

| Interval | Storage window | Start | End |
| --- | --- | --- | --- |
| Unknown prefix | 109.002669–110.986003 | unknown | unknown |
| Observed provisional start context | 110.986003–171.019336 | provisional | unknown |

The second window uses the existing open-ended source-duration convention.
Actual observations in this diagnostic end at 113.986003 seconds: no observations,
facts or end evidence are generated for the unprocessed remainder. The prefix
and provisional interval are storage keys, not proven in-game R1/R2 numbering.

### Tests and comparison

51 Package/export/Strict boundary tests PASS in 50.61 seconds; 44 practical
producer/application/accuracy/export tests PASS in 26.45 seconds (these sets
share export tests). Full source mypy: 127 files PASS. Ruff and whitespace
checks PASS. Tests cover menu-prefix retention, unknown-only input, cuts/gaps,
no formal events, zero completeness, and prior practical/Strict contracts.

| Metric | Before retention change, same actual inputs | Current | Delta |
| --- | ---: | ---: | ---: |
| Storage Packages | 1 | 2 | +1 unknown fragment |
| Observed timestamps inside Package extents | 181 | 300 | +119 |
| Formal boundary events | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 historical run | Not rerun | Not measured |

New artifacts: `r2_wide_current_phase_inputs.json`,
`r2_wide_practical_replay.json`, `r2_wide_practical_packages.json` under
`e2e_reports/match_001`. The Package diagnostic binds archived reader fingerprints
separately from current builder/replay fingerprints and includes original input
hashes, actual observed coverage and previous/current metrics. No new manual GT
was created. Wrong-reader counts for the entire wider window have not been
independently reviewed and are not inferred from confidence.

Remaining blockers: wider R1 start/end intervals, R1-to-R2 whole-source continuity,
no-false-end verification after 114 seconds, independent holdout qualification,
exact truth-time precision, sampled/canonical E2E, full regression and CI/PR.
Local zero extra candidates does not certify whole-video negative assertions.

## Wider R1 temporal evidence and full regression checkpoint

The actual common analyzer processed every native frame in the requested wider
R1 windows, with the unchanged profile and a separate calibration prefix:

| Window | Native frames | Timer available | Score pair available | Result matches | Wall seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Start, 3–6 seconds | 180 | 146 | 143 | 0 | 361.039288 |
| End, 72–77 seconds | 300 | 101 | 181 | 52 | 647.200831 |

Practical replay of each independently observed continuous window yielded:

| Boundary | Previous short-window candidate | Wider-window candidate | Delta | Confirmation time |
| --- | ---: | ---: | ---: | ---: |
| R1 start | 4.102669271 | 4.102669271 | 0 | 4.202669271 |
| R1 end | 74.486002604 | 74.486002604 | 0 | 75.369335938 |

Each wider window produced exactly one provisional boundary, no additional
start/end candidate and zero local source breaks. Formal events remain zero.
The start retained the actual transient timer displays rather than replacing
values. The end uses the observed score-change candidate with delayed result
corroboration; no GT-nearest selection or conversion of confirmation time into
boundary time occurred. The windows are separate temporal validations, not a
proof of uninterrupted lifecycle between R1 start, R1 end and R2 start.

Artifacts under `e2e_reports/match_001`:
`r1_start_wide_current_phase_inputs.json`,
`r1_end_wide_current_phase_inputs.json`, `r1_wide_practical_replay.json`.
No new reader qualification or exact point-time truth was generated. ±0.1-second
precision remains unverified and canonical assertions were not reevaluated.

Full pytest with both external Validation Pack environment paths configured
completed: **2561 PASS, 6 SKIP, 1800.33 seconds**. Skips: optional full-source HUD
anchor test (its distinct source environment was not enabled), local Tesseract
unavailable, host-native Windows path test, and three PowerShell tests. The
optional HUD anchor test runs a different whole-video/default-layout acceptance
path; it was not silently substituted for the current-profile temporal checks.
This is a complete local test-suite run with explicit skipped scope, not Windows
CI or canonical full-video accuracy certification. Ruff and diff checks PASS;
full production mypy remains 127 files PASS from the preceding unchanged-source
checkpoint. Production source was frozen throughout these fingerprint-sensitive
validations. No full canonical E2E was started because formal actual-source
qualification and whole-match continuity gates remain open.

Next integration work: efficient continuous whole-source practical collection,
full Match Package/observation association and source-negative coverage, separate
precision report with independently reviewed exact times where available,
sampled evaluation and remote Linux/Windows CI. The three provisional candidates
are not a claim of 30 canonical PASS or resolution of the 29 package FAILs.

## Native storage feasibility measurement

Before starting whole-source practical collection, measured existing source PNG
storage in the two already-used 30-frame native development windows. All
prediction/encoder comparisons retained exactly identical native PTS, timebase
and decoded pixels; original source SHA checks and existing native decode
coverage/terminal checks remained active. No recognition ran in this benchmark.

| PNG prediction / compression level | R1 window MiB | R2 window MiB | R1 wall seconds | R2 wall seconds | Sample-based full estimate GiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| none / 1 | 37.33 | 45.16 | 20.34 | 20.10 | Not production choice |
| up / 1, current production | 30.82 | 36.60 | 19.91 | 19.37 | 11.260 |
| up / 6, diagnostic only | 26.28 | 31.44 | 27.72 | 29.46 | 9.640 |
| up / 9, diagnostic only | 25.59 | 30.68 | 86.73 | 92.64 | 9.397 |

The estimate uses source metadata duration×FPS and these window averages. It is
not measured whole-video storage or a guarantee that any budget suffices.
Nevertheless the current samples do not support claiming the default 8 GiB
budget will complete this video. The collector currently buffers the entire
source before recognition. Raising the budget alone still requires actual disk
headroom; observed filesystem free space was approximately 16 GiB before this
benchmark. No full decode was launched merely to test an expected capacity limit.

Higher compression was measured through a diagnostic-only encoder-command wrapper
around the existing budgeted native decoder. No production default was changed.
Level 9 costs approximately 4.4–4.8 times the decode wall time of current `up/1`
for these windows and still has an estimate above 8 GiB; it is rejected as the
solution. Level 6 also does not resolve the estimated default-budget problem.
No lossy format, resize, frame skipping, parallel decode or weakened integrity
check was introduced.

Artifacts: `practical_native_storage_measurement.json` and
`practical_native_compression_measurement.json` under `e2e_reports/match_001`.
They bind source/contract or baseline-report hashes, frame counts, storage,
runtime and exact PTS/pixel equivalence. Production code and qualification files
are unchanged, so this checkpoint adds evidence rather than new qualification.

Next required implementation: bound retained native-frame storage while
preserving one continuous analyzer/geometry/temporal sequence, source coverage
and terminal verification. Repeated independent analyzer calls per chunk would
reset geometry/classifier state and are not an acceptable substitute. Existing
Strict collection behavior must remain unchanged. Whole-match Practical
completion remains unproven until that collection path or an explicitly adequate
budget is validated on the entire actual source.

## Bounded native source-replay decoder foundation

`video/native_replay.py` adds an alternative verified storage entrance; it is
not yet selected by the application Practical collector. Strict PNG decoding is
unchanged. A full initial FFmpeg BGR decode verifies physical-origin-to-EOF probe
PTS and records each pixel SHA-256 before exposing any frame descriptor. On-demand
sequential replay reads the original SHA-bound video, checks measured pixel
hashes, and verifies full decoder PTS coverage and source hash at each completed
pass. Backward requests restart a verified storage pass, not an analyzer call.
Partial passes are drained/verified at normal context exit; errors abort and clear
cache. Handles cannot be read after context exit. Returned images are copies,
protecting immutable cached pixels against reader mutation.

The decoder retains at most four raw frames and reserves additional buffer space
for transient read/copy allocations. The configured 64 MiB bound describes this
source buffer, not total application RAM. Frame hashes/probe metadata and analyzer
observations still occupy memory. Decode logs are temporary; PNGs are not retained.
`ReplayNativeSourceFrame` explicitly identifies original video path/hash rather
than pretending that a PNG file exists. The common `NativeSourceFrame.read_image`
reader entrance supports this descriptor without changing recognition logic.
Blocking byte transport with read/wait timeout guards is used; there is one
FFmpeg decoder per storage pass, with no parallel recognition or frame skipping.

Actual whole-source decoder validation:

| Metric | Existing whole-PNG design | Source replay validation |
| --- | --- | --- |
| Retained PNG capacity | Sample estimate 11.260 GiB | 0 PNG files |
| Verified source native frames | Not measured in storage benchmark | 10259 |
| Verified PTS span | Not measured in storage benchmark | 0.036003–171.002669 seconds |
| Actual reference pixel comparisons | Local codec comparisons | 780, zero mismatches |
| Maximum observed frame cache | All retained PNG assets | 4 raw frames |
| Initial full verification wall seconds | Not measured | 889.374779 |
| Initial/replay/terminal wall seconds | Not measured | 1596.657132 |

The 780 reference comparisons use hashes from the current R1 start/end and R2
wider diagnostic archives, with exact PTS/timebase binding. All remaining initial
frames have measured hashes and full PTS verification; this is not a claim that
they were all independently compared to PNGs or semantically reviewed. The
Linux diagnostic peak RSS was 320664 KiB; it includes its temporary whole-video
hashing allocation and interpreter/imports, and is not the native cache size.
Artifact: `e2e_reports/match_001/practical_native_replay_actual_source.json`.
No recognition, boundary qualification, Package build or canonical E2E ran in
this whole-source decoder benchmark. No speed improvement over whole PNG decode
is claimed; repeat decoding adds CPU cost while removing full-PNG disk retention.

Five new synthetic-video decoder tests PASS: PNG/PTS equivalence, repeated and
backward reads, bounded cache/copy isolation, invalid budget/timeout, source
mutation, pixel mutation, incomplete PTS rejection before publication and closed
handle rejection. Full source mypy: 128 files PASS. Ruff and diff checks PASS.
Existing full-suite result still predates this new decoder; it is not reused as
proof of this module's full integration.

Remote CI at prior HEAD `de195ce`: Linux validation succeeded; Windows verification
failed. Most Windows failures originate in the shared fixture decoding Japanese
input-contract JSON through cp1252. This fixture now explicitly reads UTF-8.
Two path-key tests used native backslashes but indexed POSIX manifest keys; their
relative fixture keys now use `as_posix`. The selected start/scene/replay tests
PASS locally (46 tests, 22.29 seconds). A separate existing Windows native-budget
cleanup failure reports a locked `decode.log`; its cause remains unresolved.
Do not report Windows CI green or this draft PR ready to merge.

Next step: connect verified source replay to common Practical collection with
configuration/fingerprints, preserve one whole analyzer invocation, test provider
selection/terminal behavior, and investigate the Windows decoder cleanup failure.
Whole-source lifecycle, false-end coverage, precise timing and canonical metrics
remain unverified. The broad goal stays active.

## Practical source-replay application integration

`VideoService.native_replay` now exposes the validated physical-origin-to-EOF
source entrance. The common collector accepts `NativeLifecycleOptions` storage
mode `png` (legacy/default API) or `replay` (explicit Practical only). Replay has
a separate positive memory-buffer allowance, default 64 MiB. Strict rejects an
explicit replay request before qualification and otherwise retains exactly its
existing PNG decoder arguments. Unsupported/missing verified providers fail
closed; there is no silent switch between storage entrances.

Application bootstrap selects replay only when the user opts into Practical.
The existing PNG allowance remains persisted for compatibility and explicit PNG
API consumers; it is not presented as the replay cache limit. The settings
notice explains that Practical does not retain all source PNGs. The configured
HUD profile remains unchanged: development diagnostic sidecars are not adopted
by changing the storage entrance.

Both storage entrances supply the entire native frame sequence to the same
single analyzer call and retain source metadata/cadence, profile/input-contract,
qualification overlay and terminal checks. No per-chunk calibration or temporal
classifier reset occurs. Source replay verifies every frame but does not change
formal boundary admission, owner facts, thresholds or canonical sampling.
The qualification code fingerprint now includes `video/native_replay.py`.
Existing resume fingerprint serialization already includes all native option
fields, so different storage mode/buffer and decoder code cannot reuse an old
practical checkpoint or qualification inadvertently.

Tests: 44 practical/provider/decoder/bootstrap/pipeline wiring tests PASS in
42.93 seconds. A final 17-test practical application selection PASS in 18.54
seconds after adding an explicit one-analyzer-call assertion. Cases include
both entrances with valid/missing/stale qualification, unchanged PNG arguments,
replay memory arguments, terminal qualification-file mutation, start-only formal
qualification, unsupported options and Strict replay rejection. Full source
mypy: 128 files PASS; Ruff and diff checks PASS. These selections are not a new
full pytest/canonical E2E run.

| Capability | Previous | Current |
| --- | --- | --- |
| Application Practical storage entrance | Whole retained PNG collection | Verified source replay |
| Continuous analyzer invocation | One | One, explicitly tested |
| Strict default native entrance | PNG | PNG |
| Actual whole-source replay decoder evidence | 10259 frames verified | Same decoder; application wiring tested synthetically |
| Actual whole-source Practical recognizer/Packages | Unverified | Still unverified |
| Canonical PASS / FAIL / NE | Historical 23 / 55 / 4 | Not rerun; delta unmeasured |

Latest fetched main remains `27c8465`, an ancestor of this branch. No main merge
was performed. Remaining work: actual whole-source Practical recognition and
Package safety, reader qualification/exact-time accuracy, Windows file-lock CI
failure diagnosis, full regression/CI after integration, sampled/canonical
acceptance where qualified. Replay reduces retained source storage, but adds
verified decode passes; no recognition speedup is asserted.

## Source replay integration regression and Windows cleanup

The complete local regression after application source-replay integration passed:
**2573 PASS, 6 SKIP, 1819.47 seconds**. Ruff passed; mypy passed for 128 source
files. The six skips retain the previously documented optional real-source HUD,
Tesseract, host-native Windows path and PowerShell limitations. This is not a new
canonical real-video E2E run and provides no new boundary-accuracy result.

Linux Basic CI passed at `322ea97`. Windows verification at that commit completed
with four failures: two decoder temporary-log cleanup failures and two scene
cohort test path-key inconsistencies. Its 2565 passes and 10 skips do not establish
Windows certification. The earlier UTF-8 fixture failure is absent in this run.

The Windows installation log confirms Chocolatey created an FFmpeg executable
shim. On early decoder rejection, terminating that launcher can leave the encoder
child holding `decode.log` or `replay.log`. The Windows workflow now resolves the
installed package's actual encoder directory, requires its paired ffprobe, and
places that directory ahead of the shim for this step and subsequent steps.
Missing or ambiguous binaries fail setup explicitly. Existing preinstalled direct
binaries retain their existing path. Runtime decoder cleanup and its assertions
remain unchanged; the final Windows rerun is needed to verify the launcher fix.

The scene cohort tests now use native `Path` string keys consistently with the
existing frozen-file verifier, including the deliberately omitted key. This
corrects the earlier incomplete POSIX-key fixture adjustment; no qualification
requirement or production recognizer was changed.
